"""Treino e artefato dos estimadores do Inferidor para a integração.

    python -m integracao.modelos treinar        # grava os dois artefatos
    python -m integracao.modelos conferir       # carrega e confere a compatibilidade

Reaproveita **sem alteração** as classes, a partição e o procedimento de
`inferidor.selecao` — a rodada que produziu os números da monografia (rede
(256, 128), α = 1e-4; árvores com taxa 0,05; limiar por sufixo na validação;
modelos finais reajustados em todo o treino com os limiares da validação).
Não havia artefato salvo da rede (`inferidor/rede.joblib` nunca foi gravado),
de modo que "reutilizar a rede existente" significa retreinar a mesma
configuração com as mesmas sementes; a reprodução das métricas de teste é
conferida em `M1` e registrada no artefato.

Acréscimos, todos escolhidos **só na validação** (pré-registro):
* θ — limiar de abstenção sobre κ, a confiança das decisões de tipo;
* τ — limiar do conflito anotado × proposto (regra de `inferidor.selecao`).

O artefato guarda o que a inferência precisa para reproduzir o treino:
nomes e ordem dos 81 atributos, máscara de colunas informativas, classes,
limiares, versões das bibliotecas e os levantamentos de cada partição.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from inferidor import dados as D  # noqa: E402
from inferidor.avaliacao import _matriz  # noqa: E402
from inferidor.modelos import SEMENTE, agrupa_raros  # noqa: E402
from inferidor.selecao import Arvores, Rede, ajusta_limiares, prob_simbolo  # noqa: E402

EXPERIMENTO = RAIZ / "experimento_integracao"
DIR_MODELOS = EXPERIMENTO / "modelos"

#: Configurações escolhidas por `inferidor.selecao` (log do wiki, 2026-10-17;
#: reconferidas na reprodução da etapa 0).
CONFIGURACOES = {
    "rede": (Rede, ((256, 128), 1e-4)),
    "arvores": (Arvores, (0.05,)),
}

#: Sufixos que propõem tipo diagnóstico no núcleo (`horizontes.PROPOSTO_POR_SUFIXO`).
SUFIXOS_TIPO = ("t", "w", "i", "h", "s", "v", "f", "g", "c")
THETAS = tuple(round(x, 2) for x in np.arange(0.50, 0.951, 0.05))
PRECISAO_ALVO = 0.80
ALARME_ALVO = 0.10


def particoes(c: D.Conjunto):
    """Mesmas partições de `inferidor.selecao`: treino/teste e ajuste/validação."""
    from sklearn.model_selection import GroupShuffleSplit
    X, principal = _matriz(c.X), agrupa_raros(c.principal)
    grupos = np.array(c.grupo)
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEMENTE)
                  .split(X, principal, grupos))
    a_, v_ = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEMENTE + 1)
                  .split(X[tr], principal[tr], grupos[tr]))
    return tr, te, tr[a_], tr[v_]


def kappa(ps_linha: np.ndarray, sufixos_candidato: set[str], aplicaveis=SUFIXOS_TIPO) -> float:
    """Menor confiança entre as decisões sobre os sufixos de tipo do candidato."""
    confs = []
    for j, s in enumerate(D.SUFIXOS_LIDOS):
        if s not in aplicaveis:
            continue
        p = float(ps_linha[j])
        confs.append(p if s in sufixos_candidato else 1.0 - p)
    return min(confs) if confs else 0.0


def sufixos_decididos(modelo, ps_linha: np.ndarray) -> set[str]:
    return {s for j, s in enumerate(D.SUFIXOS_LIDOS) if ps_linha[j] >= modelo.limiares[j]}


def escolhe_theta(modelo, X, principal, sufixos) -> tuple[float, list]:
    """θ pela regra pré-registrada, nos horizontes B de símbolo com tipo."""
    idx_tipo = [D.SUFIXOS_LIDOS.index(s) for s in SUFIXOS_TIPO]
    sel = np.array([p == "B" and sufixos[i, idx_tipo].sum() > 0 for i, p in enumerate(principal)])
    _, ps = modelo.proba(X[sel])
    verd = sufixos[sel]
    linhas = []
    for i in range(len(ps)):
        cand = sufixos_decididos(modelo, ps[i]) & set(SUFIXOS_TIPO)
        alvo = {s for s in SUFIXOS_TIPO if verd[i, D.SUFIXOS_LIDOS.index(s)]}
        linhas.append((kappa(ps[i], cand), bool(cand), cand == alvo))
    curva = []
    escolhido = 1.0
    for t in THETAS:
        aceitos = [ok for k, inf, ok in linhas if inf and k >= t]
        prec = sum(aceitos) / len(aceitos) if aceitos else None
        curva.append({"theta": t, "cobertura": len(aceitos) / len(linhas), "precisao": prec,
                      "n": len(aceitos)})
        if escolhido == 1.0 and prec is not None and prec >= PRECISAO_ALVO:
            escolhido = t
    return escolhido, curva


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def treinar(destino: Path = DIR_MODELOS) -> dict:
    import joblib
    import sklearn
    from sklearn.metrics import f1_score
    destino.mkdir(parents=True, exist_ok=True)
    c = D.do_bdsolos()
    X, principal = _matriz(c.X), agrupa_raros(c.principal)
    sufixos, grupos = np.array(c.sufixos), np.array(c.grupo)
    tr, te, a, v = particoes(c)
    lev = {"treino": sorted(set(grupos[tr])), "teste": sorted(set(grupos[te])),
           "ajuste": sorted(set(grupos[a])), "validacao": sorted(set(grupos[v]))}
    (destino / "particao_levantamentos.json").write_text(
        json.dumps(lev, ensure_ascii=False, indent=1), encoding="utf-8")
    resumo = {"horizontes": len(X), "particao": {k: len(x) for k, x in
              (("treino", tr), ("teste", te), ("ajuste", a), ("validacao", v))}}
    for nome, (Familia, cfg) in CONFIGURACOES.items():
        m_v = Familia(*cfg).fit(X[a], principal[a], sufixos[a])
        ajusta_limiares(m_v, X[v], sufixos[v])
        theta, curva = escolhe_theta(m_v, X[v], principal[v], sufixos[v])
        rot_v = [[(p, frozenset(s for s, b in zip(D.SUFIXOS_LIDOS, row) if b))]
                 for p, row in zip(principal[v], sufixos[v])]
        tau = float(np.quantile(1 - prob_simbolo(m_v, X[v], rot_v), 1 - ALARME_ALVO))
        final = Familia(*cfg).fit(X[tr], principal[tr], sufixos[tr])
        final.limiares = m_v.limiares
        pp, sp = final.predict(X[te])
        m1 = {"principal_acuracia": float((pp == principal[te]).mean()),
              "f1_macro_sufixos": float(f1_score(sufixos[te], sp, average="macro", zero_division=0)),
              "n_teste": int(len(te))}
        meta = {"nome": nome, "descricao": final.nome, "configuracao": cfg,
                "atributos": D.nomes_atributos(), "sufixos": list(D.SUFIXOS_LIDOS),
                "classes_principal": [str(x) for x in final.p.classes_],
                "colunas_informativas": [bool(x) for x in final.colunas],
                "limiares": [float(x) for x in final.limiares], "theta": theta, "curva_theta": curva,
                "tau_conflito": tau, "M1_teste": m1, "semente": SEMENTE,
                "versoes": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                            "numpy": np.__version__},
                "treinado_em": "ajuste+validação (levantamentos de treino); limiares, θ e τ na validação"}
        meta["id"] = f"{nome}-{_sha({k: meta[k] for k in ('configuracao', 'limiares', 'theta', 'tau_conflito', 'M1_teste')})[:12]}"
        joblib.dump({"modelo": final, "meta": meta}, destino / f"{nome}.joblib")
        (destino / f"{nome}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                                                              default=str), encoding="utf-8")
        resumo[nome] = {"id": meta["id"], "theta": theta, "tau": tau, **m1}
        print(f"{nome}: {final.nome} | θ = {theta} | τ = {tau:.4f} | teste: principal "
              f"{m1['principal_acuracia']:.3f}, F1 macro {m1['f1_macro_sufixos']:.3f}")
    (destino / "resumo_treino.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1,
                                                           default=str), encoding="utf-8")
    return resumo


class Estimador:
    """Interface comum aos dois estimadores: probabilidades por horizonte."""

    def __init__(self, caminho: Path):
        import joblib
        self.caminho = Path(caminho)
        pacote = joblib.load(self.caminho)
        self.modelo, self.meta = pacote["modelo"], pacote["meta"]
        if self.meta["atributos"] != D.nomes_atributos():
            raise ValueError("atributos do artefato diferem dos de inferidor.dados — "
                             "treino e inferência incompatíveis")
        if tuple(self.meta["sufixos"]) != D.SUFIXOS_LIDOS:
            raise ValueError("sufixos do artefato diferem de inferidor.dados.SUFIXOS_LIDOS")
        self.id = self.meta["id"]
        self.nome = self.meta["nome"]
        self.theta = float(self.meta["theta"])
        self.tau = float(self.meta["tau_conflito"])
        self.limiares = np.array(self.meta["limiares"])
        self.classes = list(self.modelo.p.classes_)

    def proba(self, linhas: list[list]) -> tuple[np.ndarray, np.ndarray]:
        """`linhas` são vetores de `inferidor.dados.atributos`, na mesma ordem."""
        X = _matriz(linhas)
        if X.shape[1] != len(self.meta["atributos"]):
            raise ValueError(f"{X.shape[1]} atributos; o artefato espera {len(self.meta['atributos'])}")
        return self.modelo.proba(X)


def carregar(nome: str, diretorio: Path = DIR_MODELOS) -> Estimador:
    return Estimador(diretorio / f"{nome}.joblib")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=("treinar", "conferir"))
    args = ap.parse_args(argv)
    if args.acao == "treinar":
        treinar()
    else:
        for nome in CONFIGURACOES:
            e = carregar(nome)
            print(nome, e.id, "θ", e.theta, "τ", round(e.tau, 4), e.meta["M1_teste"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
