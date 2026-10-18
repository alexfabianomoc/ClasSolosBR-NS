"""Reconciliação das métricas a partir dos registros por perfil (JSONL).

    python reconcilia.py v2      # lê resultados/etapa1_integracao/*.jsonl (rodada v2)
    python reconcilia.py v3      # lê auditoria-v3-2026-10-18/resultados/*.jsonl

Grava, em reconciliacao/<rodada>/:
  perfis.csv         uma linha por perfil × variante, com todos os eventos
  sobreposicao.md    contagens, definições, sobreposição de eventos, +0,008 reproduzido
  contagens.json     os mesmos números, estruturados

Nada aqui reexecuta o núcleo: só relê o que o experimento gravou.
"""
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
AUD = AQUI.parent
EXP = AUD.parent
RODADA = sys.argv[1] if len(sys.argv) > 1 else "v2"
FONTE = EXP / "resultados" / "etapa1_integracao" if RODADA == "v2" else AUD / "resultados"
SAIDA = AQUI / RODADA
SAIDA.mkdir(exist_ok=True)
SEMENTE, REPS = 20261019, 2000


def boot(grupos, fn, reps=REPS, semente=SEMENTE):
    """Idêntico a integracao.experimento._boot (percentil, reamostragem de grupos)."""
    rng = random.Random(semente)
    por = defaultdict(list)
    for i, g in enumerate(grupos):
        por[g].append(i)
    chaves = list(por)
    vals = []
    for _ in range(reps):
        idx = [i for g in (rng.choice(chaves) for _ in chaves) for i in por[g]]
        vals.append(fn(idx))
    vals.sort()
    return vals[int(0.025 * reps)], vals[int(0.975 * reps) - 1]


def eventos(l, v):
    """Eventos de um perfil numa variante. Definições operacionais no relatório."""
    a, r = l["A"], l[v]
    obs = a["obs"]
    ref = l.get("ref")
    referencia = (ref or {}).get("classe") if ref is not None else (l.get("registrada") or None)
    origem_ref = ("núcleo corrigido sobre os símbolos originais antes da remoção" if ref is not None
                  else "ORDEM registrada na ficha")
    cond = r.get("cond")
    resolvido = (not obs["conclusivo"]) and bool(cond and cond["conclusivo"])
    alc_cond = cond["alc"] if cond else obs["alc"]
    e = {
        "obs_classe": obs["classe"], "obs_conclusivo": obs["conclusivo"], "obs_n_alc": len(obs["alc"]),
        "referencia": referencia, "origem_referencia": origem_ref,
        "referencia_conclusiva": (ref or {}).get("conclusivo") if ref is not None else None,
        "ref_no_obs": bool(referencia) and referencia in obs["alc"],
        "acionado": r["gatilhos"] > 0, "horiz_acionados": r["gatilhos"],
        "horiz_abstencao": len(r["abstencoes"]), "horiz_com_proposta": r["propostas"] - len(r["abstencoes"]),
        "cenarios": r["cenarios"], "cenarios_compat": r["compativeis"],
        "cenarios_incompat": r["cenarios"] - r["compativeis"],
        "cenarios_fora_do_obs": len(r["violacoes_contencao"]),
        "tem_cond": cond is not None,
        "cond1_classe": cond["classe"] if cond else None,
        "cond1_conclusivo": bool(cond and cond["conclusivo"]),
        "cond1_n_alc": len(cond["alc"]) if cond else None,
        "robusta": bool(r.get("robusta")),
        "resolvido": resolvido,
        "concorda": resolvido and bool(referencia) and cond["classe"] == referencia,
        "discorda_com_ref": resolvido and bool(referencia) and cond["classe"] != referencia,
        "resolvido_sem_ref": resolvido and not referencia,
        "ref_no_cond1": bool(referencia) and referencia in alc_cond,
        "ref_excluida": bool(referencia) and referencia in obs["alc"] and referencia not in alc_cond,
        "tempo_s": r["tempo_s"],
    }
    if "cenarios_detalhe" in r:
        uni = set()
        for c in r["cenarios_detalhe"]:
            if c["compativel"]:
                uni |= set(c["alc"])
        e["uniao_alc_cenarios_compat"] = sorted(uni)
        e["ref_na_uniao"] = bool(referencia) and referencia in uni
        e["avaliacao_cenarios_completa"] = r.get("avaliacao_completa")
    # melhor resposta disponível (critério de integracao.experimento._resposta)
    if obs["conclusivo"]:
        e["melhor"] = obs["classe"]; e["melhor_origem"] = "observacional"
    elif cond and cond["conclusivo"]:
        e["melhor"] = cond["classe"]; e["melhor_origem"] = "condicional"
    else:
        e["melhor"] = None; e["melhor_origem"] = "não conclusivo"
    return e


linhas_csv, contagens, md = [], {}, [f"# Reconciliação — rodada {RODADA}", ""]
for arq in sorted(FONTE.glob("E*.jsonl")):
    nome = arq.stem
    L = [json.loads(x) for x in arq.read_text(encoding="utf-8").splitlines() if x.strip()]
    C = {"perfis": len(L)}
    md += [f"## {nome}: {len(L)} perfis", ""]
    ev = {v: [eventos(l, v) for l in L] for v in "ABC"}
    for v in "ABC":
        for l, e in zip(L, ev[v]):
            linhas_csv.append({"conjunto": nome, "perfil": l["perfil"], "grupo": l["grupo"], "variante": v, **e})
    com_ref = [i for i, e in enumerate(ev["A"]) if e["referencia"]]
    C["com_referencia"] = len(com_ref)
    C["sem_referencia"] = len(L) - len(com_ref)
    C["obs_conclusivo"] = sum(e["obs_conclusivo"] for e in ev["A"])
    C["obs_nao_conclusivo"] = len(L) - C["obs_conclusivo"]
    C["obs_nao_conclusivo_com_ref"] = sum(1 for i in com_ref if not ev["A"][i]["obs_conclusivo"])
    md.append(f"Com classe de referência definida: {len(com_ref)}; sem: {C['sem_referencia']}. "
              f"Observacional conclusiva: {C['obs_conclusivo']}; não conclusiva: {C['obs_nao_conclusivo']} "
              f"({C['obs_nao_conclusivo_com_ref']} com referência).")
    if nome in ("E1", "E3", "E3b"):
        rc = Counter((ev["A"][i]["referencia_conclusiva"]) for i in com_ref)
        C["referencia_conclusiva"] = dict((str(k), n) for k, n in rc.items())
        md.append(f"Referência conclusiva (núcleo sobre os símbolos originais): {rc.get(True, 0)}; "
                  f"referência só como classe atribuída mas não conclusiva: {rc.get(False, 0)}.")
    md += ["", "| evento (perfis) | B (rede) | C (árvores) |", "|---|---|---|"]
    for v in "BC":
        E = ev[v]
        C[v] = {
            "resolvidos": sum(e["resolvido"] for e in E),
            "concordam": sum(e["concorda"] for e in E),
            "discordam_com_ref": sum(e["discorda_com_ref"] for e in E),
            "resolvidos_sem_ref": sum(e["resolvido_sem_ref"] for e in E),
            "ref_excluida": sum(e["ref_excluida"] for e in E),
            "ref_excluida_e_discorda": sum(e["ref_excluida"] and e["discorda_com_ref"] for e in E),
            "ref_excluida_nao_conclusivo": sum(e["ref_excluida"] and not e["cond1_conclusivo"] for e in E),
            "discorda_sem_exclusao": sum(e["discorda_com_ref"] and not e["ref_excluida"] for e in E),
            "acionados": sum(e["acionado"] for e in E),
            "abstencao_total": sum(e["acionado"] and e["horiz_com_proposta"] == 0 for e in E),
            "sem_cenario_compat": sum(e["acionado"] and not e["tem_cond"] for e in E),
            "com_cenario_incompat": sum(e["cenarios_incompat"] > 0 for e in E),
            "cenarios_fora_do_obs": sum(e["cenarios_fora_do_obs"] for e in E),
            "cond_nao_conclusiva": sum(e["tem_cond"] and not e["cond1_conclusivo"] for e in E),
            "robustas": sum(e["robusta"] for e in E),
            "melhor_certa": sum(e["melhor"] is not None and e["melhor"] == e["referencia"] for e in E if e["referencia"]),
            "melhor_errada": sum(e["melhor"] is not None and e["melhor"] != e["referencia"] for e in E if e["referencia"]),
        }
        if E and "ref_na_uniao" in E[0]:
            C[v]["ref_fora_da_uniao_dos_cenarios"] = sum(bool(e["referencia"]) and e["tem_cond"] and e["ref_no_obs"]
                                                         and not e["ref_na_uniao"] for e in E)
            C[v]["avaliacao_cenarios_incompleta"] = sum(e["acionado"] and e["tem_cond"] and
                                                        not e["avaliacao_cenarios_completa"] for e in E)
    rotulos = [("acionados (≥ 1 horizonte acionado)", "acionados"),
               ("abstenção em todos os horizontes acionados", "abstencao_total"),
               ("acionado sem cenário compatível", "sem_cenario_compat"),
               ("com algum cenário rejeitado pelo núcleo (veto)", "com_cenario_incompat"),
               ("cenários fora do alcançável observacional (antes do filtro)", "cenarios_fora_do_obs"),
               ("cenário 1 compatível mas não conclusivo", "cond_nao_conclusiva"),
               ("**resolvidos** (obs. não conclusiva → cenário 1 conclusivo)", "resolvidos"),
               ("— concordam com a referência", "concordam"),
               ("— discordam da referência", "discordam_com_ref"),
               ("— sem referência definida", "resolvidos_sem_ref"),
               ("**referência excluída** (no alcançável obs., fora do cenário 1)", "ref_excluida"),
               ("— por classe condicional conclusiva discordante", "ref_excluida_e_discorda"),
               ("— com cenário 1 não conclusivo que já não a contém", "ref_excluida_nao_conclusivo"),
               ("discordantes sem exclusão (referência fora do alcançável obs.)", "discorda_sem_exclusao"),
               ("robustas (todos os cenários compatíveis conclusivos e iguais)", "robustas"),
               ("melhor resposta certa (perfis com referência)", "melhor_certa"),
               ("melhor resposta errada (perfis com referência)", "melhor_errada")]
    if "ref_fora_da_uniao_dos_cenarios" in C["B"]:
        rotulos += [("referência fora da UNIÃO dos cenários compatíveis", "ref_fora_da_uniao_dos_cenarios"),
                    ("enumeração de cenários incompleta (orçamento)", "avaliacao_cenarios_incompleta")]
    for rot, k in rotulos:
        md.append(f"| {rot} | {C['B'][k]} | {C['C'][k]} |")
    # sobreposição B × C
    sB = {i for i, e in enumerate(ev["B"]) if e["resolvido"]}
    sC = {i for i, e in enumerate(ev["C"]) if e["resolvido"]}
    xB = {i for i, e in enumerate(ev["B"]) if e["ref_excluida"]}
    xC = {i for i, e in enumerate(ev["C"]) if e["ref_excluida"]}
    C["sobreposicao"] = {"resolvidos_B_e_C": len(sB & sC), "so_B": len(sB - sC), "so_C": len(sC - sB),
                         "excluida_B_e_C": len(xB & xC), "excl_so_B": len(xB - xC), "excl_so_C": len(xC - xB)}
    md += ["", f"Sobreposição: resolvidos em B e C {len(sB & sC)}, só B {len(sB - sC)}, só C {len(sC - sB)}; "
               f"referência excluída em B e C {len(xB & xC)}, só B {len(xB - xC)}, só C {len(xC - xB)}."]
    # reprodução das diferenças pareadas sobre a melhor resposta (universo: com referência)
    g = [L[i]["grupo"] for i in com_ref]
    C["pareadas"] = {}
    md += ["", "Diferenças pareadas sobre a **melhor resposta disponível** (universo: perfis com referência; "
               "unidade: proporção de perfis; reamostragem de grupos, percentil, 2000×, semente 20261019):", "",
           "| comparação | medida | n | soma 1ª | soma 2ª | dif./perfil | IC 95% |", "|---|---|---|---|---|---|---|"]
    for a_, b_ in (("B", "A"), ("C", "A"), ("B", "C")):
        for t in ("certa", "errada", "resolvida"):
            def ind(e):
                m = e["melhor"]
                return int(m is not None and (m == e["referencia"] if t == "certa" else
                                              m != e["referencia"] if t == "errada" else True))
            xa = [ind(ev[a_][i]) for i in com_ref]
            xb = [ind(ev[b_][i]) for i in com_ref]
            lo, hi = boot(g, lambda idx: sum(xa[i] - xb[i] for i in idx) / max(1, len(idx)))
            d = (sum(xa) - sum(xb)) / max(1, len(com_ref))
            C["pareadas"][f"{a_}x{b_}_{t}"] = {"n": len(com_ref), "soma_1": sum(xa), "soma_2": sum(xb),
                                               "dif": d, "ic95": [lo, hi]}
            md.append(f"| {a_} × {b_} | {t} | {len(com_ref)} | {sum(xa)} | {sum(xb)} | {d:+.4f} | [{lo:+.3f}; {hi:+.3f}] |")
    contagens[nome] = C
    md.append("")
campos = list(linhas_csv[0].keys())
for r in linhas_csv:
    for k in r:
        if k not in campos:
            campos.append(k)
with (SAIDA / "perfis.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=campos)
    w.writeheader()
    for r in linhas_csv:
        w.writerow({k: (";".join(v) if isinstance(v, list) else v) for k, v in r.items()})
tot = sum(c["perfis"] for c in contagens.values())
md.insert(2, f"Total de perfis nos conjuntos: **{tot}** = " + " + ".join(f"{k} {c['perfis']}" for k, c in contagens.items())
          + ". Cada perfil é contado uma vez por conjunto; E3 e E3b usam os mesmos perfis curados com corrupções diferentes, "
            "e E4 usa as fichas originais desses mesmos 94 perfis — os conjuntos não são disjuntos em perfis físicos.\n")
(SAIDA / "sobreposicao.md").write_text("\n".join(md), encoding="utf-8")
(SAIDA / "contagens.json").write_text(json.dumps(contagens, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n".join(md))
