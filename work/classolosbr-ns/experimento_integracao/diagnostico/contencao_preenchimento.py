"""Contenção sob preenchimento compatível (independe de modelo).

Para cada perfil de E1 e E3 (B com sufixo de tipo reduzido a 'B'), todo
completamento dos horizontes mascarados por Bt, Bw, Bi ou Bh (produto, até
64 combinações) tem de dar saída contida no conjunto alcançável observacional.
    python contencao_preenchimento.py [--sem-correcoes] [--conjuntos E1,E3]
"""
import argparse, copy, json, sys, time
from itertools import product
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import nucleo.avaliador as AV
from integracao.experimento import conjunto
from integracao import fluxo as FX
ap = argparse.ArgumentParser(); ap.add_argument("--sem-correcoes", action="store_true")
ap.add_argument("--conjuntos", default="E1,E3"); a = ap.parse_args()
AV.CORRECOES_INTEGRACAO = not a.sem_correcoes
alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())
t0 = time.time(); tot = {}; exemplos = []
for nome in a.conjuntos.split(","):
    n = viol = comb = 0
    for avaliado, verdadeiro, grupo, ks, origem in conjunto(nome):
        n += 1
        A = alc(AV.classificar(FX._perfil(avaliado)))
        bases = {k: avaliado["HORIZONTES"][k]["SIMB_HORIZ"] for k in ks}
        combos = list(product("twih", repeat=len(ks)))[:64]
        ruim = []
        for c in combos:
            q = copy.deepcopy(avaliado)
            for k, s in zip(ks, c):
                q["HORIZONTES"][k]["SIMB_HORIZ"] = bases[k] + s
            comb += 1
            fora = alc(AV.classificar(FX._perfil(q))) - A
            if fora:
                ruim.append(("".join(c), sorted(fora)))
        if ruim:
            viol += 1
            exemplos.append((nome, avaliado["ID_PONTO"], sorted(A), ruim[:3]))
    tot[nome] = {"perfis": n, "completamentos": comb, "perfis_com_violacao": viol}
print("correções", AV.CORRECOES_INTEGRACAO, "| %.0fs" % (time.time() - t0))
print(json.dumps(tot, ensure_ascii=False))
for e in exemplos[:15]: print("  ", e)
