"""Diagnóstico prévio às correções: (1) incidência do truncamento em
MAX_VARIANTES; (2) assinaturas de símbolo (principal + sufixos) no BDSolos,
para o catálogo de leituras do símbolo ausente."""
import json, sys
from collections import Counter
from math import prod
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "dags")); sys.path.insert(0, str(RAIZ.parents[1] / "tools"))
import bdsolos_adapter as B
from nucleo.perfil import de_dicionario, carregar_json
from nucleo.avaliador import _v_em_conflito, MAX_VARIANTES
from nucleo.horizontes import _leituras_discordam, leituras_atuais, gs

def eixos(p):
    n = []
    for h in p.horizontes:
        k = len(gs.leituras(h.simbolo)) if _leituras_discordam(h.simbolo) else 1
        if _v_em_conflito(h) is not None: k *= 2
        if k > 1: n.append(k)
    return prod(n) if n else 1

perfis, _ = B.ler_perfis()
todos = B.filtrar(perfis)
cur = [p for a in sorted((RAIZ.parents[1] / "raw" / "pykka7-smartsolos-dataset").rglob("*.json")) if not a.name.endswith("_all.json") for p in carregar_json(a)]
for nome, ps in (("BDSolos", [de_dicionario(b) for b in todos]), ("curado", cur)):
    tam = [eixos(p) for p in ps]
    print(nome, "perfis", len(ps), "com produto >", MAX_VARIANTES, ":", sum(t > MAX_VARIANTES for t in tam), "máx", max(tam))
assin = Counter()
for b in todos:
    for h in b.get("HORIZONTES") or []:
        s = h.get("SIMB_HORIZ") or ""
        for l in leituras_atuais(s)[:1]:
            a = gs.analisa(l)
            if a.reconhecido and not a.mesclado and a.principal:
                assin[(a.principal, "".join(sorted(set(x.rstrip(gs.MACRON) for x in a.sufixos))))] += 1
tot = sum(assin.values()); acum = 0
print("assinaturas distintas:", len(assin), "horizontes:", tot)
for i, (k, c) in enumerate(assin.most_common()):
    acum += c
    if i < 60 or acum / tot < 0.995:
        pass
    if acum / tot >= 0.995:
        print("99,5% em", i + 1, "assinaturas"); break
json.dump([[k[0], k[1], c] for k, c in assin.most_common()], open(Path(__file__).with_suffix(".json"), "w", encoding="utf-8"), ensure_ascii=False)
