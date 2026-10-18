"""Tabelas do relatório a partir de resultados/etapa1_integracao/resumo.json.
    python gera_tabelas.py   →  04-resultados-tabelas.md"""
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
R = json.loads((AQUI.parent / "resultados" / "etapa1_integracao" / "resumo.json").read_text(encoding="utf-8"))
NOMES = {"E1": "E1 — BDSolos-teste, ablação artificial (B com tipo → B)",
         "E2": "E2 — BDSolos-teste, incompletude natural",
         "E3": "E3 — curado, ablação artificial",
         "E3b": "E3b — curado, símbolo do 1º B apagado",
         "E4": "E4 — fichas originais pré-curadoria"}


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else f"{a}/0"


L = ["# 4. Resultados (gerado por `gera_tabelas.py` a partir de `resumo.json`)", ""]
for nome in ("E1", "E2", "E3", "E3b", "E4"):
    if nome not in R:
        continue
    x = R[nome]
    L += [f"## {NOMES[nome]}", "",
          f"Perfis: **{x['perfis']}** ({x['grupos']} grupos — levantamentos no BDSolos, perfis no curado); "
          f"falhas de execução A/B/C: {x['falhas']}; verificações finais violadas: {x['verificacoes_violadas']}.",
          f"Invariância da resposta observacional A = B = C: **{pct(x['M8_invariancia_observacional'], x['avaliados'])}**; "
          f"da Camada de Versão: {pct(x['M8_invariancia_versao'], x['avaliados'])}.",
          f"Efeito das correções (A0 × A, resposta observacional diferente): {x['efeito_correcoes_A0_x_A']['perfis_com_saida_diferente']} perfis."]
    if "M5_ref_no_alcancavel_A" in x:
        a, b = x["M5_ref_no_alcancavel_A"]
        a0, b0 = x["M5_ref_no_alcancavel_A0"]
        L.append(f"Classe com os símbolos verdadeiros dentro do alcançável observacional: A {pct(a, b)}; A0 {pct(a0, b0)}.")
    L += ["", "| | A (sem inferência) | B (rede) | C (árvores) |", "|---|---|---|---|"]
    v = x["variantes"]

    def linha(rot, f):
        L.append(f"| {rot} | " + " | ".join(f(v[k]) for k in "ABC") + " |")
    linha("horizontes acionados", lambda d: str(d["horizontes_acionados"]))
    linha("horizontes com proposta", lambda d: pct(d["horizontes_com_proposta"], d["horizontes_acionados"]) if d["propostas"] else "—")
    linha("abstenções (motivo: n)", lambda d: "; ".join(f"{k}: {n}" for k, n in d["abstencoes"].items()) or "—")
    linha("candidatos bem-formados", lambda d: pct(d["candidatos_bem_formados"], d["candidatos"]) if d["candidatos"] else "—")
    linha("cenários compatíveis", lambda d: pct(d["cenarios_compativeis"], d["cenarios"]) if d["cenarios"] else "—")
    linha("incompatibilidades", lambda d: "; ".join(f"{k}: {n}" for k, n in d["incompatibilidades"]) or "—")
    linha("**violações de contenção**", lambda d: str(d["violacoes_contencao"]))
    linha("observacional não conclusiva", lambda d: str(d["obs_nao_conclusivos"]))
    linha("→ condicional conclusiva (cenário 1)", lambda d: pct(d["M3_resolvidos_cond_cenario1"], d["obs_nao_conclusivos"]))
    linha("→ condicional robusta (todos os cenários)", lambda d: pct(d["M3_resolvidos_cond_robusta"], d["obs_nao_conclusivos"]))
    linha("condicionais concordantes / discordantes", lambda d: f"{d['M4_cond_concordantes']} / {d['M4_cond_discordantes']}")
    linha("robustas concordantes", lambda d: str(d["M4_robusta_concordantes"]))
    linha("referência no alcançável (cenário 1 ou obs.)", lambda d: str(d["M4_ref_alcancavel_cond"]))
    linha("conflitos sinalizados (horizontes)", lambda d: str(d["conflitos_sinalizados"]))
    linha("divergentes no Explicador (perfis)", lambda d: str(d["divergentes_explicador"]))
    linha("hipóteses de anotação geradas / verificadas", lambda d: f"{d['hip_anotacao_geradas']} / {d['hip_anotacao_verificadas']}")
    linha("perfis com hipótese de anotação verificada", lambda d: str(d["perfis_com_hip_anotacao_verificada"]))
    linha("tempo por perfil: média / mediana / p95 (s)", lambda d: f"{d['tempo_medio_s']:.2f} / {d['tempo_mediano_s']:.2f} / {d['tempo_p95_s']:.2f}")
    linha("cenários avaliados", lambda d: str(d["cenarios"]))
    L += ["", f"Referência das concordâncias: {v['A']['M4_referencia']}.", "",
          "Comparações pareadas sobre a **melhor resposta disponível** (observacional se conclusiva; "
          "senão a condicional do cenário 1, que continua sendo condicional). Diferença por perfil, "
          "IC 95% por reamostragem de grupos, discordantes (a favor da 1ª / da 2ª) e McNemar exato:", "",
          "| comparação | medida | n | 1ª | 2ª | dif./perfil | IC 95% | discordantes | p |", "|---|---|---|---|---|---|---|---|---|"]
    for k, c in x["comparacoes_pareadas"].items():
        a_, b_ = k.split("_vs_")
        for t, y in c.items():
            L.append(f"| {a_} × {b_} | {t} | {y['n']} | {y[a_]} | {y[b_]} | {y['diferenca_por_perfil']:+.3f} | "
                     f"[{y['ic95_por_grupo'][0]:+.3f}; {y['ic95_por_grupo'][1]:+.3f}] | {y['discordantes'][0]}/{y['discordantes'][1]} | {y['mcnemar_p']:.3g} |")
    if nome == "E4":
        e = x["E4"]
        L += ["", "**Conflitos e Explicador nas fichas originais (referência: trocas substantivas de símbolo da curadoria):**", "",
              "| | B (rede) | C (árvores) |", "|---|---|---|"]
        def l4(rot, f):
            L.append(f"| {rot} | {f(e['B'])} | {f(e['C'])} |")
        l4("trocas sinalizadas pelo conflito", lambda d: pct(*d["conflito_tp"]))
        l4("falso alerta (conflito sem troca)", lambda d: pct(*d["conflito_falso_alerta"]))
        l4("horizontes acionados com troca: n / abstenções / assinatura = curada",
           lambda d: f"{d['propostas_em_horizontes_acionados_com_troca']['n']} / {d['propostas_em_horizontes_acionados_com_troca']['abstencoes']} / {d['propostas_em_horizontes_acionados_com_troca']['assinatura_igual_a_curada']}")
        l4("casos de referência para Acerto@k (divergentes com troca)", lambda d: str(d["acerto_at_k"]["casos_de_referencia"]))
        l4("Acerto@1 / @3 (horizonte e assinatura)", lambda d: f"{d['acerto_at_k']['horizonte_e_assinatura']['1']} / {d['acerto_at_k']['horizonte_e_assinatura']['3']}")
        l4("Acerto@1 / @3 (só horizonte)", lambda d: f"{d['acerto_at_k']['so_horizonte']['1']} / {d['acerto_at_k']['so_horizonte']['3']}")
        L.append(f"\nHipóteses numéricas idênticas entre A, B e C: {e['numericas_identicas_entre_variantes']}/{x['avaliados']} perfis.")
    L.append("")
(AQUI / "04-resultados-tabelas.md").write_text("\n".join(L), encoding="utf-8")
print("ok")
