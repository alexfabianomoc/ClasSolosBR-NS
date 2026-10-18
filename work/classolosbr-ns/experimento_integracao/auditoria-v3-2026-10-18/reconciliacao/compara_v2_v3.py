"""Comparação v2 × v3, perfil a perfil (mesmos perfis, mesmos modelos).

A única mudança no núcleo é C5; no fluxo, a robustez sob orçamento. Separa:
  * mudança na resposta observacional (A v2 × A v3) — efeito de C5;
  * mudança no cenário 1 de B/C com observacional inalterada — efeito sobre a integração;
  * robustez retirada por avaliação incompleta (só v3 sabe).
Grava reconciliacao/v2_x_v3.md e v2_x_v3.csv.
"""
import csv, json
from collections import Counter
from pathlib import Path
AQUI = Path(__file__).resolve().parent
AUD = AQUI.parent
V2 = AUD.parent / "resultados" / "etapa1_integracao"
V3 = AUD / "resultados"


def carrega(p):
    return {json.loads(l)["perfil"]: json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}


md = ["# Comparação v2 × v3 (por perfil)", ""]
linhas = []
for c in ("E1", "E2", "E3", "E3b", "E4"):
    if not (V3 / f"{c}.jsonl").exists():
        continue
    a, b = carrega(V2 / f"{c}.jsonl"), carrega(V3 / f"{c}.jsonl")
    comuns = [p for p in a if p in b]
    obs_mud = [p for p in comuns if a[p]["A"]["obs"] != b[p]["A"]["obs"]]
    md += [f"## {c}: {len(comuns)} perfis em comum (v2 {len(a)}, v3 {len(b)})", "",
           f"Resposta observacional diferente (efeito de C5): **{len(obs_mud)}**"]
    for p in obs_mud[:10]:
        md.append(f"* `{p}`: {a[p]['A']['obs']['classe']} {a[p]['A']['obs']['alc']} → "
                  f"{b[p]['A']['obs']['classe']} {b[p]['A']['obs']['alc']}")
        linhas.append({"conjunto": c, "perfil": p, "variante": "A", "tipo": "observacional",
                       "v2": json.dumps(a[p]["A"]["obs"], ensure_ascii=False),
                       "v3": json.dumps(b[p]["A"]["obs"], ensure_ascii=False)})
    for v in "BC":
        cond_mud = [p for p in comuns if p not in obs_mud and a[p][v].get("cond") != b[p][v].get("cond")]
        rob = Counter((bool(a[p][v].get("robusta")), bool(b[p][v].get("robusta"))) for p in comuns)
        incompleta = sum(1 for p in comuns if b[p][v].get("avaliacao_completa") is False)
        md.append(f"* {v}: cenário 1 diferente com observacional igual: **{len(cond_mud)}**; "
                  f"robusta v2→v3 (sim→não): {rob.get((True, False), 0)}, (não→sim): {rob.get((False, True), 0)}; "
                  f"enumeração incompleta na v3: {incompleta}")
        for p in cond_mud:
            linhas.append({"conjunto": c, "perfil": p, "variante": v, "tipo": "cenario1",
                           "v2": json.dumps(a[p][v].get("cond"), ensure_ascii=False),
                           "v3": json.dumps(b[p][v].get("cond"), ensure_ascii=False)})
    md.append("")
with (AQUI / "v2_x_v3.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["conjunto", "perfil", "variante", "tipo", "v2", "v3"])
    w.writeheader(); w.writerows(linhas)
(AQUI / "v2_x_v3.md").write_text("\n".join(md), encoding="utf-8")
print("\n".join(md))
