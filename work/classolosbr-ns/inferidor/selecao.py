"""Rodada de melhoria do Inferidor (decisão do usuário de 2026-10-17, opção B).

    python -m inferidor.selecao [--json SAIDA.json] [--salvar]

Regra: **toda escolha é feita numa validação interna** — 20% dos
levantamentos de treino —, e a partição de teste e as fichas do conjunto
curado só entram uma vez, ao fim, com tudo fixado.

Escolhas:
1. arquitetura da rede: camadas (64,), (128, 64), (256, 128) × regularização
   L2 1e-4, 1e-3, 1e-2; árvores de gradiente com taxa de aprendizado 0,05,
   0,1 e 0,2 (busca do mesmo porte, para a comparação seguir justa);
   critério: acurácia do principal + F1 macro dos sufixos, na validação;
2. limiar por sufixo, que maximiza o F1 daquele sufixo na validação (nos dois
   modelos);
3. sinal de conflito: 1 − P(símbolo anotado), com P(símbolo) = P(principal) ×
   Π P(valor anotado de cada sufixo lido), segundo a rede; limiar fixado
   **antes** de olhar o conjunto curado, como o que sinaliza 10% dos
   horizontes da validação, cujos símbolos se presumem, na maioria, corretos.
   Reporta-se também a AUC do sinal contra as trocas substantivas, que não
   depende de limiar.
"""
from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import dados as D
from .avaliacao import ORIGINAIS, _leitura_rotulos, _matriz, _medidas
from .modelos import SEMENTE, MaisFrequente, agrupa_raros, colunas_informativas
from nucleo.estatistica import fmt, wilson

CAMADAS = ((64,), (128, 64), (256, 128))
ALFAS = (1e-4, 1e-3, 1e-2)
TAXAS = (0.05, 0.1, 0.2)
LIMIARES = np.round(np.arange(0.05, 0.96, 0.05), 2)
ALARME_ALVO = 0.10


class Rede:
    def __init__(self, camadas=(128, 64), alfa=1e-4):
        self.camadas, self.alfa = camadas, alfa
        self.nome = f"rede neural (MLP {camadas}, α={alfa:g})"
        self.limiares = np.full(len(D.SUFIXOS_LIDOS), 0.5)

    def _pipe(self):
        return make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=self.camadas, alpha=self.alfa,
                          early_stopping=True, validation_fraction=0.1, max_iter=300,
                          random_state=SEMENTE))

    def fit(self, X, principal, sufixos):
        self.colunas = colunas_informativas(X)
        X = X[:, self.colunas]
        self.p = self._pipe().fit(X, principal)
        self.s = self._pipe().fit(X, sufixos)
        return self

    def proba(self, X):
        X = X[:, self.colunas]
        return self.p.predict_proba(X), self.s.predict_proba(X)

    def predict(self, X):
        pp, ps = self.proba(X)
        return self.p.classes_[pp.argmax(1)], (ps >= self.limiares).astype(int)


class Arvores:
    def __init__(self, taxa=0.1):
        self.taxa = taxa
        self.nome = f"não neural (árvores de gradiente, taxa {taxa:g})"
        self.limiares = np.full(len(D.SUFIXOS_LIDOS), 0.5)

    def fit(self, X, principal, sufixos):
        self.colunas = colunas_informativas(X)
        X = X[:, self.colunas]
        kw = dict(max_iter=300, learning_rate=self.taxa, random_state=SEMENTE)
        self.p = HistGradientBoostingClassifier(**kw).fit(X, principal)
        self.s = [HistGradientBoostingClassifier(**kw).fit(X, sufixos[:, j])
                  if sufixos[:, j].min() != sufixos[:, j].max() else float(sufixos[0, j])
                  for j in range(sufixos.shape[1])]
        return self

    def proba(self, X):
        X = X[:, self.colunas]
        ps = np.column_stack([np.full(len(X), m) if isinstance(m, float)
                              else m.predict_proba(X)[:, 1] for m in self.s])
        return self.p.predict_proba(X), ps

    def predict(self, X):
        pp, ps = self.proba(X)
        return self.p.classes_[pp.argmax(1)], (ps >= self.limiares).astype(int)


def ajusta_limiares(modelo, X, sufixos):
    """Limiar por sufixo que maximiza o F1 daquele sufixo (na validação)."""
    _, ps = modelo.proba(X)
    for j in range(sufixos.shape[1]):
        if sufixos[:, j].sum() == 0:
            continue
        f1s = [f1_score(sufixos[:, j], ps[:, j] >= t, zero_division=0) for t in LIMIARES]
        modelo.limiares[j] = LIMIARES[int(np.argmax(f1s))]


def criterio(modelo, X, principal, sufixos):
    pp, sp = modelo.predict(X)
    return float((pp == principal).mean()) + f1_score(sufixos, sp, average="macro", zero_division=0)


def prob_simbolo(modelo, X, rotulos_por_linha):
    """P(símbolo anotado) segundo o modelo; com mais de uma leitura, a maior."""
    pp, ps = modelo.proba(X)
    classes = list(modelo.p.classes_)
    saida = []
    for i, rotulos in enumerate(rotulos_por_linha):
        melhor = 0.0
        for principal, sufixos in rotulos:
            k = classes.index(principal) if principal in classes else (
                classes.index("outro") if "outro" in classes else None)
            p = pp[i, k] if k is not None else 0.0
            for j, s in enumerate(D.SUFIXOS_LIDOS):
                p *= ps[i, j] if s in sufixos else 1 - ps[i, j]
            melhor = max(melhor, p)
        saida.append(melhor)
    return np.array(saida)


def seleciona(familia, configs, Xa, pa, sa, Xv, pv, sv):
    resultados = []
    for cfg in configs:
        m = familia(*cfg).fit(Xa, pa, sa)
        ajusta_limiares(m, Xv, sv)
        resultados.append((criterio(m, Xv, pv, sv), cfg, m))
        print(f"   {m.nome:<52} validação: {resultados[-1][0]:.4f}")
    return max(resultados, key=lambda r: r[0])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--salvar", action="store_true")
    args = ap.parse_args(argv)
    print("Inferidor — seleção na validação interna e avaliação final (§4.2.5)")
    print("=" * 78)
    c = D.do_bdsolos()
    X, principal = _matriz(c.X), agrupa_raros(c.principal)
    sufixos, grupos, ordem = np.array(c.sufixos), np.array(c.grupo), np.array(c.ordem_solo)
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEMENTE)
                  .split(X, principal, grupos))
    a_, v_ = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEMENTE + 1)
                  .split(X[tr], principal[tr], grupos[tr]))
    a, v = tr[a_], tr[v_]
    print(f"ajuste: {len(a)} horizontes ({len(set(grupos[a]))} lev.); validação: {len(v)} "
          f"({len(set(grupos[v]))} lev.); teste: {len(te)} ({len(set(grupos[te]))} lev.)")
    saida = {"ajuste": len(a), "validacao": len(v), "teste": len(te)}

    print("\nSeleção — rede")
    _, cfg_r, _ = seleciona(Rede, list(product(CAMADAS, ALFAS)),
                            X[a], principal[a], sufixos[a], X[v], principal[v], sufixos[v])
    print("Seleção — árvores")
    _, cfg_a, _ = seleciona(Arvores, [(t,) for t in TAXAS],
                            X[a], principal[a], sufixos[a], X[v], principal[v], sufixos[v])
    saida["escolhas"] = {"rede": {"camadas": cfg_r[0], "alfa": cfg_r[1]}, "arvores": {"taxa": cfg_a[0]}}

    # Limiares e limiar do conflito, na validação, com os modelos ajustados em `a`.
    rede_v = Rede(*cfg_r).fit(X[a], principal[a], sufixos[a])
    ajusta_limiares(rede_v, X[v], sufixos[v])
    arv_v = Arvores(*cfg_a).fit(X[a], principal[a], sufixos[a])
    ajusta_limiares(arv_v, X[v], sufixos[v])
    rot_v = [[(p, frozenset(s for s, b in zip(D.SUFIXOS_LIDOS, row) if b))]
             for p, row in zip(principal[v], sufixos[v])]
    sinal_v = 1 - prob_simbolo(rede_v, X[v], rot_v)
    tau = float(np.quantile(sinal_v, 1 - ALARME_ALVO))
    print(f"\nlimiar do conflito (sinaliza {ALARME_ALVO:.0%} da validação): 1 − P(símbolo) ≥ {tau:.3f}")
    saida["limiares_rede"] = dict(zip(D.SUFIXOS_LIDOS, map(float, rede_v.limiares)))
    saida["limiares_arvores"] = dict(zip(D.SUFIXOS_LIDOS, map(float, arv_v.limiares)))
    saida["tau_conflito"] = tau

    # Avaliação final no teste: modelos reajustados em todo o treino, limiares da validação.
    rede = Rede(*cfg_r).fit(X[tr], principal[tr], sufixos[tr]); rede.limiares = rede_v.limiares
    arv = Arvores(*cfg_a).fit(X[tr], principal[tr], sufixos[tr]); arv.limiares = arv_v.limiares
    freq = MaisFrequente().fit(X[tr], principal[tr], sufixos[tr])
    print("\nInferência — partição de teste (usada uma vez)")
    saida["inferencia"] = {}
    for chave, m, pred in (("rede", rede, rede.predict(X[te])), ("arvores", arv, arv.predict(X[te])),
                           ("frequente", freq, freq.predict(X[te], principal_anotado=principal[te]))):
        saida["inferencia"][chave] = _medidas(m.nome, principal[te], pred[0], sufixos[te], pred[1], grupos[te])
    print("\nF1 por sufixo no teste (rede | árvores) e positivos:")
    pr, pa_ = rede.predict(X[te]), arv.predict(X[te])
    for j, s in enumerate(D.SUFIXOS_LIDOS):
        print(f"   {s}  {f1_score(sufixos[te][:, j], pr[1][:, j], zero_division=0):.3f} | "
              f"{f1_score(sufixos[te][:, j], pa_[1][:, j], zero_division=0):.3f}   "
              f"({int(sufixos[te][:, j].sum())})")

    from collections import Counter
    print("\nPor ordem de solo (200+ horizontes de teste): principal / F1 macro — rede | árvores")
    saida["por_ordem"] = {}
    for o, n in Counter(ordem[te]).most_common():
        if n < 200:
            continue
        sel = ordem[te] == o
        lin = {}
        for chave, pred in (("rede", pr), ("arvores", pa_)):
            lin[chave] = {"acuracia": float((principal[te][sel] == pred[0][sel]).mean()),
                          "f1_macro": f1_score(sufixos[te][sel], pred[1][sel], average="macro",
                                               zero_division=0)}
        saida["por_ordem"][o] = {"n": int(n), **lin}
        print(f"   {o:<14} {n:>5}   {fmt(lin['rede']['acuracia'])} / {lin['rede']['f1_macro']:.3f}"
              f"  |  {fmt(lin['arvores']['acuracia'])} / {lin['arvores']['f1_macro']:.3f}")

    # Uso efetivo: rede reajustada em todo o acervo; limiares e τ da validação.
    final = Rede(*cfg_r).fit(X, principal, sufixos); final.limiares = rede_v.limiares
    linhas = []
    for caminho in sorted(ORIGINAIS.glob("*.json")):
        bruto = json.loads(caminho.read_text(encoding="utf-8"))["items"][0]
        hs, ordem_h = bruto.get("HORIZONTES") or [], D.em_ordem(bruto)
        curado = {x["horizonte"]: x["curado"] for x in bruto.get("_ALTERACOES", [])
                  if x["campo"] == "SIMB_HORIZ"}
        for k, h in enumerate(hs):
            orig = _leitura_rotulos(h.get("SIMB_HORIZ") or "")
            if not orig:
                continue
            fin = _leitura_rotulos(curado.get(k, h.get("SIMB_HORIZ") or ""))
            i = next(j for j, x in enumerate(ordem_h) if x is h)
            linhas.append({"x": D.atributos(bruto, i, ordem_h), "orig": orig,
                           "subst": bool(fin) and all(o != fin[0] for o in orig)})
    Xc = _matriz([l["x"] for l in linhas])
    sinal = 1 - prob_simbolo(final, Xc, [l["orig"] for l in linhas])
    y = np.array([l["subst"] for l in linhas])
    flag = sinal >= tau
    sin, fa = int((flag & y).sum()), int((flag & ~y).sum())
    auc = roc_auc_score(y, sinal)
    print("\nUso efetivo — fichas originais do conjunto curado (usadas uma vez)")
    print(f"   horizontes: {len(y)}; trocas substantivas: {int(y.sum())}")
    print(f"   AUC do sinal contra as trocas: {auc:.3f}")
    print(f"   sinalizadas: {sin}/{int(y.sum())} {fmt(wilson(sin, int(y.sum())))}")
    print(f"   falso alarme: {fa}/{int((~y).sum())} {fmt(wilson(fa, int((~y).sum())))}")
    print(f"   precisão do sinal: {sin}/{sin + fa} {fmt(wilson(sin, sin + fa)) if sin + fa else '—'}")
    saida["uso_efetivo"] = {"horizontes": len(y), "trocas": int(y.sum()), "auc": auc,
                            "sinalizadas": sin, "falso_alarme": fa, "sem_troca": int((~y).sum())}
    if args.salvar:
        import joblib
        joblib.dump({"rede": final, "tau": tau}, D.RAIZ / "inferidor" / "rede.joblib")
    if args.json:
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
