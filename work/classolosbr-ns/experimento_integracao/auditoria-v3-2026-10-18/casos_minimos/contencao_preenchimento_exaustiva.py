"""Contenção sob preenchimento compatível — enumeração EXAUSTIVA (auditoria v3).

Substitui, para fins de evidência, o diagnóstico da rodada v2
(`diagnostico/contencao_preenchimento.py`), que truncava cada perfil nas 64
primeiras combinações (21 perfis afetados; 8.972 de 14.540 avaliadas).

Universo: perfis de E1 (BDSolos-teste) e E3 (curado) — os horizontes B cujo
sufixo de tipo foi removido ('2Bt2' → '2B'). Catálogo por horizonte mascarado:
  ∅ (continua 'B', sem tipo), t, w, i, h.
`s` não entra por ser equivalente a `h` no 1º nível (ambos propõem B espódico em
`horizontes.PROPOSTO_POR_SUFIXO`); g, f, c, v, m não entram porque o 'B' sem
sufixo os nega (decisão de 2026-10-15). Sem limite: 5^k combinações por perfil.
Propriedade: alcançável(preenchido) ⊆ alcançável(mascarado), 5ª edição.
    python contencao_preenchimento_exaustiva.py [--sem-correcoes]
"""
import argparse, copy, json, sys, time
from itertools import product
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
import nucleo.avaliador as AV
from integracao.experimento import conjunto
from integracao import fluxo as FX
ap = argparse.ArgumentParser(); ap.add_argument("--sem-correcoes", action="store_true"); a = ap.parse_args()
AV.CORRECOES_INTEGRACAO = not a.sem_correcoes
alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())
t0 = time.time(); tot = {}; ex = []
for nome in ("E1", "E3"):
    n = viol = comb = 0
    for avaliado, verdadeiro, grupo, ks, origem in conjunto(nome):
        n += 1
        A = alc(AV.classificar(FX._perfil(avaliado)))
        bases = {k: avaliado["HORIZONTES"][k]["SIMB_HORIZ"] for k in ks}
        ruim = []
        for c in product(("", "t", "w", "i", "h"), repeat=len(ks)):
            q = copy.deepcopy(avaliado)
            for k, s in zip(ks, c):
                q["HORIZONTES"][k]["SIMB_HORIZ"] = bases[k] + s
            comb += 1
            fora = alc(AV.classificar(FX._perfil(q))) - A
            if fora:
                ruim.append(("".join(x or "∅" for x in c), sorted(fora)))
        if ruim:
            viol += 1; ex.append((nome, avaliado["ID_PONTO"], sorted(A), ruim[:3]))
    tot[nome] = {"perfis": n, "combinacoes": comb, "perfis_com_violacao": viol}
print(json.dumps({"correcoes": AV.CORRECOES_INTEGRACAO, "segundos": round(time.time() - t0), **tot}, ensure_ascii=False))
for e in ex[:20]: print("  ", e)
