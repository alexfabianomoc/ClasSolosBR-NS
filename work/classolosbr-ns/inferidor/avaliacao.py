"""Avaliação do Inferidor de Horizonte Diagnóstico (monografia, §4.2.5 e Quadro 7).

    python -m inferidor.avaliacao [--json SAIDA.json] [--salvar]

Duas partes, como a §4.2.5 define:

1. **Inferência**, sobre partição de teste do acervo nacional que separa
   levantamentos inteiros (80% / 20%): acurácia do horizonte principal e F1
   macro sobre os 17 sufixos lidos, no todo e por ordem de solo, contra as
   duas linhas de base. Intervalos: Wilson para a acurácia; reamostragem por
   levantamento para acurácia e F1.
2. **Uso efetivo**, sobre as fichas originais transcritas do conjunto curado
   (que não entram no treino): a proporção das trocas de símbolo da curadoria
   que o conflito entre o símbolo anotado e o proposto sinaliza. Conta como
   troca **substantiva** a que muda o horizonte principal ou algum dos 17
   sufixos lidos, depois de modernizada a notação do símbolo original; a
   simples atualização de notação (`IIC1` → `2C`, `A11` → `Ap`) não conta.
   Reporta-se também o falso alarme: conflitos em horizontes sem troca
   substantiva.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupShuffleSplit

from . import dados as D
from .modelos import SEMENTE, Arvores, MaisFrequente, Rede, agrupa_raros

sys.path.insert(0, str(D.RAIZ))
from nucleo.estatistica import fmt, wilson  # noqa: E402

ORIGINAIS = D.RAIZ / "transcricao" / "originais"
MINIMO_ORDEM = 200      # horizontes de teste para reportar uma ordem
REPETICOES = 1000


def _matriz(linhas):
    return np.array([[np.nan if v is None else v for v in x] for x in linhas], dtype=float)


def _bootstrap(grupos, fn, reps=REPETICOES, semente=SEMENTE):
    """Intervalo de 95% por reamostragem de levantamentos; `fn(indices)`."""
    rng = random.Random(semente)
    por = defaultdict(list)
    for i, g in enumerate(grupos):
        por[g].append(i)
    chaves = list(por)
    vals = []
    for _ in range(reps):
        idx = [i for g in (rng.choice(chaves) for _ in chaves) for i in por[g]]
        vals.append(fn(np.array(idx)))
    vals.sort()
    return vals[int(0.025 * reps)], vals[int(0.975 * reps) - 1]


def _medidas(nome, p_true, p_pred, s_true, s_pred, grupos):
    acertos = int((p_true == p_pred).sum())
    n = len(p_true)
    f1 = f1_score(s_true, s_pred, average="macro", zero_division=0)
    lo_a, hi_a = _bootstrap(grupos, lambda i: float((p_true[i] == p_pred[i]).mean()))
    lo_f, hi_f = _bootstrap(grupos, lambda i: f1_score(s_true[i], s_pred[i], average="macro",
                                                         zero_division=0))
    w = wilson(acertos, n)
    print(f"  {nome:<48} principal {acertos}/{n} {fmt(w)} [lev.: {fmt(lo_a)}–{fmt(hi_a)}]"
          f"   F1 macro (17 sufixos) {f1:.3f} [lev.: {lo_f:.3f}–{hi_f:.3f}]")
    por_sufixo = f1_score(s_true, s_pred, average=None, zero_division=0)
    return {"principal_acertos": acertos, "n": n, "principal_wilson": list(w),
            "principal_lev": [lo_a, hi_a], "f1_macro": f1, "f1_macro_lev": [lo_f, hi_f],
            "f1_por_sufixo": dict(zip(D.SUFIXOS_LIDOS, map(float, por_sufixo)))}


def inferencia(c: D.Conjunto, saida: dict):
    X = _matriz(c.X)
    principal = agrupa_raros(c.principal)
    sufixos = np.array(c.sufixos)
    grupos = np.array(c.grupo)
    ordem = np.array(c.ordem_solo)
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEMENTE)
                  .split(X, principal, grupos))
    print(f"treino: {len(tr)} horizontes de {len(set(grupos[tr]))} levantamentos; "
          f"teste: {len(te)} horizontes de {len(set(grupos[te]))} levantamentos")
    saida["particao"] = {"treino": len(tr), "teste": len(te),
                         "lev_treino": len(set(grupos[tr])), "lev_teste": len(set(grupos[te]))}
    modelos = {"rede": Rede(), "arvores": Arvores(), "frequente": MaisFrequente()}
    pred = {}
    for chave, m in modelos.items():
        m.fit(X[tr], principal[tr], sufixos[tr])
        if chave == "frequente":
            pred[chave] = m.predict(X[te], principal_anotado=principal[te])
        else:
            pred[chave] = m.predict(X[te])
    print("\nInferência — partição de teste por levantamento")
    saida["inferencia"] = {}
    for chave, m in modelos.items():
        pp, sp = pred[chave]
        saida["inferencia"][chave] = _medidas(m.nome, principal[te], pp, sufixos[te], sp, grupos[te])
    print("\nF1 por sufixo (rede | árvores | mais frequente) e positivos no teste:")
    for j, s in enumerate(D.SUFIXOS_LIDOS):
        vals = [saida["inferencia"][k]["f1_por_sufixo"][s] for k in ("rede", "arvores", "frequente")]
        print(f"   {s}  {vals[0]:.3f} | {vals[1]:.3f} | {vals[2]:.3f}   ({int(sufixos[te][:, j].sum())})")
    print(f"\nPor ordem de solo (ordens com {MINIMO_ORDEM}+ horizontes de teste): "
          "acurácia do principal e F1 macro — rede | árvores | mais frequente")
    saida["por_ordem"] = {}
    for o, n in Counter(ordem[te]).most_common():
        if n < MINIMO_ORDEM:
            continue
        sel = ordem[te] == o
        linha = {}
        partes = []
        for k in ("rede", "arvores", "frequente"):
            pp, sp = pred[k]
            acc = float((principal[te][sel] == pp[sel]).mean())
            f1 = f1_score(sufixos[te][sel], sp[sel], average="macro", zero_division=0)
            linha[k] = {"acuracia": acc, "f1_macro": f1}
            partes.append(f"{fmt(acc)} / {f1:.3f}")
        saida["por_ordem"][o] = {"n": int(n), **linha}
        print(f"   {o:<14} {n:>5}   " + "  |  ".join(partes))
    return modelos["rede"]


def _leitura_rotulos(simbolo: str):
    """Rótulos possíveis do símbolo anotado: um por leitura atual."""
    s = (simbolo or "").strip()
    moderno = D.gs.moderniza(s)
    leituras = [moderno] if moderno else (D.gs.leituras(s) or [s])
    saida = []
    for l in leituras:
        a = D.gs.analisa(l)
        if a.reconhecido and not a.mesclado and a.principal:
            saida.append((a.principal, frozenset(x for x in a.sufixos if x in D.SUFIXOS_LIDOS)))
    return saida


def uso_efetivo(rede: Rede, saida: dict):
    """Trocas de símbolo da curadoria sinalizadas pelo conflito anotado × proposto."""
    linhas = []
    for caminho in sorted(ORIGINAIS.glob("*.json")):
        bruto = json.loads(caminho.read_text(encoding="utf-8"))["items"][0]
        hs = bruto.get("HORIZONTES") or []
        ordem = D.em_ordem(bruto)
        curado = {a["horizonte"]: a["curado"] for a in bruto.get("_ALTERACOES", [])
                  if a["campo"] == "SIMB_HORIZ"}
        for k, h in enumerate(hs):
            i = next(j for j, x in enumerate(ordem) if x is h)
            original = h.get("SIMB_HORIZ") or ""
            orig = _leitura_rotulos(original)
            if not orig:
                continue
            final = _leitura_rotulos(curado.get(k, original))
            substantiva = bool(final) and all(o != final[0] for o in orig)
            linhas.append({"perfil": bruto.get("ID_PONTO"), "h": k, "original": original,
                           "curado": curado.get(k, original), "x": D.atributos(bruto, i, ordem),
                           "orig": orig, "final": final, "substantiva": substantiva})
    X = _matriz([l["x"] for l in linhas])
    pp, sp = rede.predict(X)
    for l, p, s in zip(linhas, pp, sp):
        proposto = (str(p), frozenset(x for x, b in zip(D.SUFIXOS_LIDOS, s) if b))
        l["proposto"] = proposto
        l["conflito"] = all(proposto != o for o in l["orig"])
        l["acerta_curado"] = bool(l["final"]) and proposto == l["final"][0]
    subst = [l for l in linhas if l["substantiva"]]
    resto = [l for l in linhas if not l["substantiva"]]
    sin = sum(l["conflito"] for l in subst)
    fa = sum(l["conflito"] for l in resto)
    ac = sum(l["acerta_curado"] for l in subst)
    print("\nUso efetivo — fichas originais do conjunto curado (fora do treino)")
    print(f"   horizontes avaliáveis: {len(linhas)}; trocas substantivas de símbolo pela curadoria: {len(subst)}")
    print(f"   trocas sinalizadas pelo conflito: {sin}/{len(subst)} {fmt(wilson(sin, len(subst)))}")
    print(f"   proposta igual ao símbolo curado: {ac}/{len(subst)} {fmt(wilson(ac, len(subst)))}")
    print(f"   falso alarme (conflito sem troca substantiva): {fa}/{len(resto)} {fmt(wilson(fa, len(resto)))}")
    for l in subst[:12]:
        print(f"      {l['perfil'][-28:]:<28} {l['original']:>8} → {l['curado']:<8} "
              f"proposto {l['proposto'][0]}{''.join(sorted(l['proposto'][1]))}"
              f"{'  ← sinalizado' if l['conflito'] else ''}")
    saida["uso_efetivo"] = {"avaliaveis": len(linhas), "trocas_substantivas": len(subst),
                            "sinalizadas": sin, "proposta_igual_curado": ac,
                            "falso_alarme": fa, "sem_troca": len(resto)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--salvar", action="store_true", help="grava a rede treinada em todo o acervo")
    args = ap.parse_args(argv)
    print("Inferidor de Horizonte Diagnóstico — avaliação (§4.2.5)")
    print("=" * 78)
    c = D.do_bdsolos()
    print(f"horizontes rotulados: {len(c.X)} de {len(set(c.perfil))} perfis e "
          f"{len(set(c.grupo))} levantamentos; fora do treino: {c.descartados}")
    saida = {"horizontes": len(c.X), "descartados": c.descartados}
    inferencia(c, saida)
    # Para o uso efetivo, a rede é treinada no acervo inteiro: as fichas do
    # conjunto curado nunca entram no treino.
    rede = Rede().fit(_matriz(c.X), agrupa_raros(c.principal), np.array(c.sufixos))
    uso_efetivo(rede, saida)
    if args.salvar:
        import joblib
        joblib.dump(rede, D.RAIZ / "inferidor" / "rede.joblib")
        print("\nrede gravada em inferidor/rede.joblib")
    if args.json:
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=1, default=str),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
