"""Contenção sob apagamento do símbolo de B no conjunto curado: a classe
derivada com o símbolo verdadeiro tem de continuar no conjunto alcançável
quando o símbolo é apagado ('') ou reduzido ao principal ('B').
    python contencao_simbolo_apagado.py [--sem-correcoes] [--limite N]"""
import argparse, copy, json, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
import nucleo.avaliador as AV
from nucleo.perfil import de_dicionario
ap = argparse.ArgumentParser(); ap.add_argument("--sem-correcoes", action="store_true"); ap.add_argument("--limite", type=int, default=0)
a = ap.parse_args()
AV.CORRECOES_INTEGRACAO = not a.sem_correcoes
P = RAIZ.parents[1] / "raw" / "pykka7-smartsolos-dataset"
arqs = [x for x in sorted(P.rglob("*.json")) if not x.name.endswith("_all.json")]
if a.limite: arqs = arqs[:a.limite]
alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())
cont = {"": [0, 0], "B": [0, 0]}; t0 = time.time(); viol = []
for x in arqs:
    item = json.JSONDecoder().raw_decode(x.read_text(encoding="utf-8"))[0]["items"][0]
    base = AV.classificar(de_dicionario(item))
    if not base.classe: continue
    for k, h in enumerate(item["HORIZONTES"]):
        if not (h.get("SIMB_HORIZ") or "").lstrip("0123456789").startswith("B"): continue
        for novo in cont:
            it2 = copy.deepcopy(item); it2["HORIZONTES"][k]["SIMB_HORIZ"] = novo
            r = AV.classificar(de_dicionario(it2))
            cont[novo][0] += 1
            if base.classe not in alc(r):
                cont[novo][1] += 1; viol.append((item["ID_PONTO"], h["SIMB_HORIZ"], novo, base.classe, r.resumo()))
print("correções", AV.CORRECOES_INTEGRACAO, "| perfis", len(arqs), "| tempo %.0fs" % (time.time() - t0))
for novo, (n, v) in cont.items():
    print(f"  símbolo {novo!r}: {v}/{n} apagamentos tiram a classe derivada do alcançável")
for v in viol[:10]: print("   ", v)
