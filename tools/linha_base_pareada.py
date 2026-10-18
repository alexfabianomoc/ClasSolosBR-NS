"""Diferença pareada núcleo × sistema de referência, 1º nível (monografia, §5.8).

    python tools/linha_base_pareada.py

Só lê o cache da linha de base (`tools/linha_base.py coletar`). Para cada
universo — treze ordens, recorte, e os dois sem os perfis em que o sistema de
referência devolve ordem desconhecida —, reporta as duas concordâncias, os
perfis acertados só por um dos sistemas, a diferença e o intervalo de 95% por
reamostragem dos levantamentos (2.000 réplicas, semente fixa). O qui-quadrado
de McNemar é informativo e ignora o agrupamento.

Criado em 2026-10-17 na auditoria da monografia: a §5.8 comparava os
sistemas pela sobreposição de intervalos individuais.
"""
import sys, random, math
from collections import defaultdict
sys.path.insert(0, "tools"); sys.path.insert(0, "work/classolosbr-ns")
import linha_base as L
from nucleo.avaliador import classificar
from nucleo.chave5 import CHAVE_5ED
from nucleo.perfil import de_dicionario
from nucleo.avaliacao import _recorte
rec = {L.norm(x) for x in _recorte(CHAVE_5ED)}
cache = L._carrega_cache()
linhas = []
for p in L.conjuntos()["bdsolos"]:
    r = cache["respostas"].get(f"bdsolos|{p['ID_PONTO']}")
    if not r: continue
    inf = r["inferido"] or {}
    nuc = classificar(de_dicionario(p), CHAVE_5ED)
    conc = bool(nuc.classe) and not nuc.alcancaveis
    rot = L.norm(p.get("ORDEM")); sr = L.norm(inf.get("ORDEM"))
    linhas.append((str(p["ID_PONTO"]).split("|")[1], rot in rec, sr == rot, conc and L.norm(nuc.classe) == rot, sr in ("", "UNKNOWN", "DESCONHECIDO")))
def analisa(nome, sub):
    n = len(sub); a = sum(x[2] for x in sub); b = sum(x[3] for x in sub)
    so_sr = sum(1 for x in sub if x[2] and not x[3]); so_nu = sum(1 for x in sub if x[3] and not x[2])
    mc = (abs(so_sr - so_nu) - 1) ** 2 / max(1, so_sr + so_nu)
    grupos = defaultdict(list)
    for x in sub: grupos[x[0]].append(x)
    chaves = list(grupos); rng = random.Random(20261017); ds = []
    for _ in range(2000):
        amostra = [y for k in (rng.choice(chaves) for _ in chaves) for y in grupos[k]]
        ds.append((sum(y[3] for y in amostra) - sum(y[2] for y in amostra)) / len(amostra))
    ds.sort()
    print(f"{nome}: n={n} SR {a} ({100*a/n:.1f}%) núcleo {b} ({100*b/n:.1f}%) só SR {so_sr} só núcleo {so_nu} | dif (núcleo−SR) {100*(b-a)/n:+.1f} pp; IC95 por levantamento [{100*ds[50]:+.1f}; {100*ds[1949]:+.1f}] pp; McNemar χ²={mc:.1f} (ignora agrupamento)")
analisa("todas, 5.706", linhas)
analisa("recorte, Quadro 19", [x for x in linhas if x[1]])
analisa("todas, sem 'unknown' do SR", [x for x in linhas if not x[4]])
analisa("recorte, sem 'unknown' do SR", [x for x in linhas if x[1] and not x[4]])
