"""Comando de execução do fluxo integrado.

    python -m integracao.cli executar PERFIL.json [--variante A|B|C] [--registrada CLASSE]
                                      [--json SAIDA.json] [--sem-recomendacao]
                                      [--sem-explicador-numerico] [--sem-sentinela]
    python -m integracao.cli exemplos      # regenera experimento_integracao/exemplos/

Variantes: A = sem inferência aprendida; B = rede neural; C = árvores de gradiente.
PERFIL.json no formato do contrato (objeto com HORIZONTES, ou {"items": [...]}).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from . import fluxo as FX  # noqa: E402
from .inferidor import Inferidor  # noqa: E402

MODELO = {"A": None, "B": "rede", "C": "arvores"}


def _itens(caminho: Path) -> list[dict]:
    dados, _ = json.JSONDecoder().raw_decode(caminho.read_text(encoding="utf-8"))
    if isinstance(dados, dict) and "items" in dados:
        return dados["items"]
    return dados if isinstance(dados, list) else [dados]


def texto(s: dict) -> str:
    L = [f"Perfil {s.get('perfil')} — {s['variante']} — {s['edicao']}"]
    if s["status"] != "ok":
        return "\n".join(L + [f"ENTRADA INVÁLIDA: {s['entrada']['erros']}"])
    for a in s["entrada"]["avisos"]:
        L.append(f"  aviso: {a}")
    o = s["observacional"]
    L.append(f"\nRESPOSTA OBSERVACIONAL (só dados observados): {o['resumo']}")
    for p in o["pendencias"][:5]:
        L.append(f"  pendência: {p}")
    v = s["versao"]
    L.append(f"\nCAMADA DE VERSÃO: 5ª → {v['sob_5a']}; 6ª → {v['sob_6a']}")
    for c in v["categorias"]:
        L.append(f"  · {c}")
    sen = s["sentinela"]
    if sen["gramatica"] or sen["anomalias"]:
        L.append("\nSENTINELA (sinaliza; não decide):")
        for g in sen["gramatica"][:5]:
            L.append(f"  símbolo {g['simbolo']!r}: " + "; ".join(a["codigo"] for a in g["achados"])
                     + (f" (leitura atual: {g['leitura_atual_sugerida']})" if g["leitura_atual_sugerida"] else ""))
        for a in sen["anomalias"][:5]:
            L.append(f"  anomalia σ={a['sigma']}: {a['atributo']}({a['simbolo']}) = {a['valor']}")
    inf = s.get("inferencia", {})
    L.append(f"\nINFERIDOR: {inf.get('status')}")
    for p in inf.get("propostas", []):
        cands = ", ".join(f"{c['simbolo']} (κ={c['kappa']:.2f})" for c in p["candidatos"][:3])
        L.append(f"  horizonte {p['horizonte_id']} {p['simbolo_anotado']!r} [{p['gatilho']}]: {cands}"
                 + (f" — ABSTENÇÃO: {p['abstencao']}" if p["abstencao"] else ""))
    c = s.get("condicional", {})
    if c.get("cenarios"):
        L.append(f"\nCLASSES CONDICIONAIS ({c['cenarios_avaliados']} de {c['combinacoes_possiveis']} cenários):")
        for x in c["cenarios"]:
            subs = "; ".join(f"{y['simbolo_anotado'] or '∅'}→{y['simbolo_inferido']}" for y in x["substituicoes"])
            L.append(f"  cenário {x['cenario']} [{subs}] → {x['resultado']['resumo']}"
                     + ("" if x["compativel"] else f"  (INCOMPATÍVEL: {x['incompatibilidade']})"))
        L.append(f"  {c['aviso']}; robusta: {c['condicional_robusta']}")
    ca = s.get("conflitos_de_anotacao")
    if ca and ca["sinalizados"]:
        L.append("\nCONFLITOS ANOTADO × PROPOSTO (hipóteses de anotação; nada é alterado):")
        for x in ca["sinalizados"]:
            L.append(f"  horizonte {x['horizonte_id']} {x['simbolo_anotado']}: sinal {x['sinal']:.3f} ≥ τ "
                     f"{x['tau']:.3f}; proposto {', '.join(y['simbolo'] for y in x['candidatos'])}")
    e = s.get("explicador", {})
    L.append(f"\nEXPLICADOR: {e.get('status')}")
    if isinstance(e.get("hipoteses_numericas"), list):
        for h in e["hipoteses_numericas"][:3]:
            L.append(f"  numérica: {h['atributo']}({h['horizonte']}) {h['valor_informado']:g} → "
                     f"{h['valor_proposto']:.4g} (escore {h['escore']}) — {h['natureza']}")
    if isinstance(e.get("hipoteses_de_anotacao"), list):
        for h in e["hipoteses_de_anotacao"][:3]:
            L.append(f"  anotação: horizonte {h['horizonte_id']} {h['simbolo_anotado']} → "
                     f"{h['simbolo_hipotetico']} ({h['forma']}, {h['origem']}): "
                     f"{'VERIFICADA' if h['verificada'] else 'não restabelece'} — {h['natureza']}")
    pd = s.get("proxima_determinacao", {})
    if pd.get("candidatas"):
        L.append("\nPRÓXIMA DETERMINAÇÃO:")
        for x in pd["candidatas"][:3]:
            L.append(f"  {x['unidade']} em {x['horizonte']}: ganho {x['ganho_bits']} bit, "
                     f"conclui em {100 * x['p_concluir']:.0f}% dos desfechos simulados")
    else:
        L.append(f"\nPRÓXIMA DETERMINAÇÃO: {pd.get('status', 'nenhuma medição reduz o alcançável')}")
    L.append(f"\nVERIFICAÇÕES: {s['verificacoes']}  ({s['tempo_s']} s)")
    return "\n".join(L)


def executar(args) -> int:
    nome = MODELO[args.variante]
    inf = FX.inferidor_padrao(nome)
    for item in _itens(Path(args.arquivo)):
        cfg = FX.Configuracao(inferidor=inf, classe_registrada=args.registrada,
                              recomendar=not args.sem_recomendacao,
                              explicador_numerico=not args.sem_explicador_numerico,
                              detector=None if args.sem_sentinela else
                              FX.detector_de_referencia(item.get("ID_PONTO")))
        s = FX.executar(item, cfg)
        print(texto(s))
        if args.json:
            Path(args.json).write_text(json.dumps(s, ensure_ascii=False, indent=1, default=str),
                                       encoding="utf-8")
    return 0


def exemplos() -> int:
    """Exemplos de saída com rastreabilidade (arquivos JSON + texto)."""
    from .testes import EstimadorFalso, curado, mascarar_b
    pasta = RAIZ / "experimento_integracao" / "exemplos"
    pasta.mkdir(parents=True, exist_ok=True)
    casos = []
    pe1 = curado("GeoTab_PE_001_Lagoa_dos_Gatos")
    casos.append(("01-PE_001-B-mascarado", mascarar_b(pe1), None,
                  "Bt1/Bt2 reduzidos a B: a observacional não conclui; o Inferidor completa o tipo"))
    k = next(i for i, h in enumerate(pe1["HORIZONTES"]) if h["SIMB_HORIZ"] == "Bt1")
    ap = copy.deepcopy(pe1)
    ap["HORIZONTES"][k]["SIMB_HORIZ"] = ""
    casos.append(("02-PE_001-simbolo-ausente", ap, None, "símbolo do Bt1 apagado (C1 + proposta completa)"))
    err = copy.deepcopy(pe1)
    err["HORIZONTES"][k]["SIMB_HORIZ"] = "Bi1"
    casos.append(("03-PE_001-erro-de-anotacao-simulado", err, None,
                  "Bt1 anotado como Bi1: divergência; hipóteses numéricas e de anotação"))
    orig = json.loads((RAIZ / "transcricao" / "originais" / "GeoTab_PE_003_Camocim_de_Sao_Felix.json")
                      .read_text(encoding="utf-8"))["items"][0]
    casos.append(("04-PE_003-ficha-original", orig, None,
                  "ficha original (B1, B21, B22 em notação antiga): acionamento natural"))
    casos.append(("05-RN_007-testemunha", curado("GeoTab_RN_007_Acu"), None,
                  "o caso-testemunha (unknown no sistema de referência)"))
    casos.append(("06-PE_025-edicoes", curado("GeoTab_PE_025_Barreiros"), None,
                  "saídas diferentes sob 5ª e 6ª"))
    indice = []
    for nome, item, reg, desc in casos:
        for var in ("A", "B", "C"):
            # com símbolo ausente, cada classificação percorre o catálogo (C1): sem recomendação
            ausente = any(not str(h.get("SIMB_HORIZ") or "").strip() for h in item["HORIZONTES"])
            cfg = FX.Configuracao(inferidor=FX.inferidor_padrao(MODELO[var]), classe_registrada=reg,
                                  detector=FX.detector_de_referencia(item.get("ID_PONTO")),
                                  k_doadores=15, recomendar=var == "A" and not ausente)
            s = FX.executar(item, cfg)
            base = pasta / f"{nome}-{var}"
            base.with_suffix(".json").write_text(json.dumps(s, ensure_ascii=False, indent=1, default=str),
                                                 encoding="utf-8")
            base.with_suffix(".txt").write_text(texto(s), encoding="utf-8")
        indice.append(f"- `{nome}-{{A,B,C}}` — {desc}")
    s = FX.executar(mascarar_b(pe1), FX.Configuracao(inferidor=Inferidor(None, "artefato removido"),
                                                     recomendar=False))
    (pasta / "07-PE_001-modelo-indisponivel.txt").write_text(texto(s), encoding="utf-8")
    indice.append("- `07-PE_001-modelo-indisponivel` — o fluxo segue e a observacional permanece")
    (pasta / "LEIA-ME.md").write_text(
        "# Exemplos de saída do fluxo integrado\n\nGerados por `python -m integracao.cli exemplos`. "
        "A = sem inferência aprendida; B = rede; C = árvores. O `.json` traz a saída completa, com a "
        "árvore de prova de cada cenário condicional anotada (`simbolos_inferidos`: símbolo, modelo, "
        "κ, cenário); o `.txt` é a leitura resumida.\n\n" + "\n".join(indice) + "\n", encoding="utf-8")
    print("\n".join(indice))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="acao", required=True)
    e = sub.add_parser("executar")
    e.add_argument("arquivo")
    e.add_argument("--variante", choices=("A", "B", "C"), default="A")
    e.add_argument("--registrada", default=None)
    e.add_argument("--json", default=None)
    e.add_argument("--sem-recomendacao", action="store_true")
    e.add_argument("--sem-explicador-numerico", action="store_true")
    e.add_argument("--sem-sentinela", action="store_true")
    sub.add_parser("exemplos")
    a = ap.parse_args(argv)
    return executar(a) if a.acao == "executar" else exemplos()


if __name__ == "__main__":
    raise SystemExit(main())
