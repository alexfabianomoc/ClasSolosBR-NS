"""Caracterização do erro "referência LATOSSOLO → classe condicional ARGISSOLO".

Universo: perfis da rodada v2 (E1, E2) em que, na rede OU nas árvores, a classe
de referência é LATOSSOLO e o cenário 1 conclui ARGISSOLO. Para cada perfil e
modelo, reexecuta o fluxo (mesmos artefatos, mesmo código da integração; núcleo
com C1–C5) e registra: símbolos anotados/originais, candidatos com κ e p(t),
p(w), p(i); se `Bw` estava entre os candidatos; o que o núcleo dá com todos os
horizontes acionados completados por `Bw` e por `Bt` (contrafactual, só para
diagnóstico — nunca usado como predição); e atributos dos horizontes acionados.

Nenhum limiar é ajustado aqui; o rótulo nunca entra como preditor.
"""
import copy, csv, json, sys
from collections import Counter
from pathlib import Path
AUD = Path(__file__).resolve().parents[1]
RAIZ = AUD.parents[1]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "dags")); sys.path.insert(0, str(RAIZ.parents[1] / "tools"))
from integracao import fluxo as FX
from integracao.experimento import conjunto
from nucleo.avaliador import classificar
from nucleo.horizontes import relacao_textural

linhas = list(csv.DictReader((AUD / "reconciliacao" / "v2" / "perfis.csv").open(encoding="utf-8")))
alvo = {}
for r in linhas:
    if r["conjunto"] in ("E1", "E2") and r["variante"] in "BC" and r["referencia"] == "LATOSSOLO" \
            and r["resolvido"] == "True" and r["cond1_classe"] == "ARGISSOLO":
        alvo.setdefault((r["conjunto"], r["perfil"]), set()).add(r["variante"])
infs = {"B": FX.inferidor_padrao("rede"), "C": FX.inferidor_padrao("arvores")}
saida = []
for cj in ("E1", "E2"):
    for avaliado, verdadeiro, grupo, ks, origem in conjunto(cj):
        chave = (cj, avaliado["ID_PONTO"])
        if chave not in alvo:
            continue
        reg = {"conjunto": cj, "perfil": chave[1], "grupo": grupo, "erro_em": sorted(alvo[chave]),
               "registrada": avaliado.get("ORDEM")}
        p = FX._perfil(avaliado)
        rt = relacao_textural(p)
        reg["relacao_textural"] = None if rt is None else round(rt, 3)
        for v, inf in infs.items():
            s = FX.executar(avaliado, FX.Configuracao(inferidor=inf, recomendar=False, explicador_numerico=False,
                                                      explicar=False))
            props = s["inferencia"].get("propostas", [])
            reg[v] = {"cenario1": s["condicional"].get("resumo_cenario_1"),
                      "propostas": [{"h": x["horizonte_id"], "anotado": x["simbolo_anotado"],
                                     "abst": x["abstencao"],
                                     "cands": [(c["simbolo"], round(c["kappa"], 3),
                                                {k: round(c["p_sufixos"][k], 3) for k in "twi"}) for c in x["candidatos"]]}
                                    for x in props],
                      "bw_entre_candidatos": any(c["simbolo"].endswith("Bw") or "w" in c["simbolo"].lstrip("0123456789B")
                                                 for x in props for c in x["candidatos"]),
                      "classes_dos_cenarios": [c["resultado"]["resumo"] for c in s["condicional"].get("cenarios", [])]}
        acion = [int(k) for k in s["gatilhos"]]
        for suf in ("w", "t"):
            q = copy.deepcopy(avaliado)
            for k in acion:
                sb = q["HORIZONTES"][k]["SIMB_HORIZ"]
                q["HORIZONTES"][k]["SIMB_HORIZ"] = sb + suf
            reg[f"nucleo_com_todos_B{suf}"] = classificar(FX._perfil(q)).resumo()
        reg["horizontes_acionados"] = [{
            "simbolo": avaliado["HORIZONTES"][k].get("SIMB_HORIZ"),
            "original": (verdadeiro["HORIZONTES"][k].get("SIMB_HORIZ") if verdadeiro else None),
            "prof": [avaliado["HORIZONTES"][k].get("LIMITE_SUP"), avaliado["HORIZONTES"][k].get("LIMITE_INF")],
            **{c: avaliado["HORIZONTES"][k].get(c) for c in ("ARGILA", "CEROSIDADE_GRAU", "ESTRUTURA_TIPO",
                                                             "ESTRUTURA_GRAU", "COR_UMIDA_MATIZ", "C_ORG")}}
            for k in acion]
        saida.append(reg)
(AUD / "latossolo" / "casos.json").write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
# resumo
res = {"perfis": len(saida), "por_conjunto": Counter(r["conjunto"] for r in saida),
       "erro_em": Counter("+".join(r["erro_em"]) for r in saida)}
for v in "BC":
    ks = [c[1] for r in saida for x in r[v]["propostas"] if not x["abst"] for c in x["cands"][:1]]
    pt = [c[2]["t"] for r in saida for x in r[v]["propostas"] if not x["abst"] for c in x["cands"][:1]]
    pw = [c[2]["w"] for r in saida for x in r[v]["propostas"] if not x["abst"] for c in x["cands"][:1]]
    res[v] = {"bw_entre_candidatos": sum(r[v]["bw_entre_candidatos"] for r in saida),
              "kappa_medio_topo": round(sum(ks) / len(ks), 3) if ks else None,
              "p_t_medio_topo": round(sum(pt) / len(pt), 3) if pt else None,
              "p_w_medio_topo": round(sum(pw) / len(pw), 3) if pw else None,
              "algum_cenario_latossolo": sum(any(c.startswith("LATOSSOLO") or "LATOSSOLO" in c.split("—")[0]
                                                 for c in r[v]["classes_dos_cenarios"]) for r in saida)}
res["nucleo_com_todos_Bw_latossolo"] = sum(r["nucleo_com_todos_Bw"].startswith("LATOSSOLO") for r in saida)
res["nucleo_com_todos_Bw"] = Counter(r["nucleo_com_todos_Bw"].split(" (")[0] for r in saida)
res["nucleo_com_todos_Bt"] = Counter(r["nucleo_com_todos_Bt"].split(" (")[0] for r in saida)
res["originais_E1"] = Counter(h["original"] for r in saida if r["conjunto"] == "E1" for h in r["horizontes_acionados"])
res["anotados_E2"] = Counter(h["simbolo"] for r in saida if r["conjunto"] == "E2" for h in r["horizontes_acionados"])
rts = [r["relacao_textural"] for r in saida if r["relacao_textural"] is not None]
res["relacao_textural"] = {"n": len(rts), "mediana": sorted(rts)[len(rts) // 2] if rts else None,
                           ">=1.5": sum(x >= 1.5 for x in rts)}
cer = Counter(h["CEROSIDADE_GRAU"] for r in saida for h in r["horizontes_acionados"])
res["cerosidade_grau_nos_acionados"] = cer
(AUD / "latossolo" / "resumo.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
