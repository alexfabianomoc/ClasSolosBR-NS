"""Gera `nucleo/dados/catalogo_simbolo_ausente.json` (correção C1, cópia experimental).

Leituras usadas pela supervalorização quando um horizonte não tem símbolo:
as assinaturas observadas no BDSolos (sem o conjunto curado), reduzidas ao que
a base de regras lê — letra(s) do horizonte principal válidas pela norma de
notação e os sufixos que propõem tipo (`t w i g h s f c v` e o `m` de `cm`) —,
completadas por todo B com um sufixo de tipo e por todo par de tipo de B com
`g`, `f`, `c` ou `v`. Símbolos fora do catálogo não são considerados: a
correção é sólida **relativamente ao catálogo** (ver teste de contenção).
"""
import json, sys
from collections import Counter
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "dags")); sys.path.insert(0, str(RAIZ.parents[1] / "tools"))
import bdsolos_adapter as B
from nucleo.horizontes import leituras_atuais, gs

REL = "twighsfcvm"
VALIDOS = {"H", "O", "A", "E", "B", "C", "F", "R", "AB", "AC", "AE", "BA", "BC", "BE",
           "CA", "CB", "EA", "EB"}
perfis, _ = B.ler_perfis()
cont = Counter()
for b in B.filtrar(perfis, sem_curado=True):
    for h in b.get("HORIZONTES") or []:
        for l in leituras_atuais(h.get("SIMB_HORIZ") or "")[:1]:
            a = gs.analisa(l)
            if a.reconhecido and not a.mesclado and a.principal in VALIDOS:
                suf = "".join(c for c in REL if c in {x.rstrip(gs.MACRON) for x in a.sufixos})
                cont[a.principal + suf] += 1
extra = {"B" + s for s in "twihsvcfg"} | {"Bcm", "Ccm"}   # litoplíntico (c + m)
extra |= {"B" + "".join(sorted(p, key=REL.index)) for t in "twi" for o in "gfcv" for p in [(t, o)]}
cat = []
for s in [k for k, _ in cont.most_common()] + sorted(extra):
    a = gs.analisa(s)
    if s not in cat and a.reconhecido and not a.mesclado:
        cat.append(s)
saida = RAIZ / "nucleo" / "dados" / "catalogo_simbolo_ausente.json"
saida.write_text(json.dumps({"procedencia": __doc__.strip().splitlines()[0],
                             "gerado_por": "experimento_integracao/diagnostico/gera_catalogo_simbolo_ausente.py",
                             "leituras": cat}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(cat), cat)
