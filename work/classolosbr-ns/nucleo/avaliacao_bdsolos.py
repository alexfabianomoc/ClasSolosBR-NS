"""Avaliação do núcleo sobre o BDSolos — a verificação fora da amostra.

    python -m nucleo.avaliacao_bdsolos [--ablacao] [--json SAIDA.json]

Conjunto (monografia, §3.2 e §3.5): perfis do BDSolos com rótulo até o 1º
nível, **corroborados** (a ordem da coluna aparece no texto da Classificação
Atual) e **sem os 40 registros que repetem 36 perfis do conjunto curado**
(`tools/dados/sobreposicao_pykka7_bdsolos.json`). O adaptador
`tools/bdsolos_adapter.py` faz a conversão e os filtros; aqui só se
classifica e se conta. Denominador esperado: 5.808.

Só o 1º nível está formalizado, de modo que a escala L0–L4 se reduz a
L0 × L1+ — a concordância na ordem.

Desfechos por perfil:

* **concorda** — o núcleo conclui a ordem registrada;
* **contém** — não conclui, mas a ordem registrada continua alcançável;
* **diverge** — a ordem registrada está fora do conjunto alcançável. Pelo
  quadro de expectativas da §3.4, cada divergência com atributos completos é
  caso de investigação.

🚨 **Compromisso da mitigação 5 (§3.5):** este conjunto **não** serve para
depurar regras. Defeito encontrado aqui é registrado e só corrigido com a
passagem da norma, e o fato é declarado no capítulo 5. Este módulo não
corrige nada; ele mede.

Intervalos: Wilson (95%) e reamostragem **por levantamento** (Código
Trabalho), porque perfis de um mesmo levantamento compartilham descritor,
laboratório e método (mitigação 11).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .avaliador import classificar
from .estatistica import bootstrap_por_grupo, fmt, wilson
from .perfil import de_dicionario

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "tools"))
import bdsolos_adapter as adaptador  # noqa: E402

#: As cinco ordens do recorte (Quadro 6).
RECORTE = ("LATOSSOLO", "ARGISSOLO", "LUVISSOLO", "ESPODOSSOLO", "CAMBISSOLO")
#: Ordens testadas antes do recorte cujo rótulo pode propagar-se para ele
#: (validade de instrumentação, §3.5; item do checklist).
PRECEDENTES = ("VERTISSOLO", "GLEISSOLO", "PLINTOSSOLO", "ESPODOSSOLO")

_ORDENS_SIBCS = re.compile(
    r"\b(organossolo|neossolo|vertissolo|espodossolo|planossolo|gleissolo|"
    r"latossolo|chernossolo|cambissolo|plintossolo|luvissolo|nitossolo|"
    r"argissolo)s?\b")


def carregar(nivel_minimo: int = 1):
    brutos, _ = adaptador.ler_perfis(com_procedencia=True)
    brutos = list(brutos.values()) if isinstance(brutos, dict) else brutos
    sel = adaptador.filtrar(brutos, nivel_minimo=nivel_minimo,
                            corroborado=True, sem_curado=True)
    return [(b, de_dicionario(b)) for b in sel]


def levantamento(id_ponto: str) -> str:
    return id_ponto.split("|")[1]


def _comparavel(texto: str) -> str:
    t = re.sub(r"\s+", " ", (texto or "").strip())
    t = re.sub(r"[.\s]+$", "", t)
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")


def estrato(bruto: dict) -> str:
    """Estrato de reclassificação — ⚠️ critério **reconstruído**, exploratório.

    🚨 2026-10-17, decisão do usuário (opção b1): a estratificação saiu da
    monografia. O critério que gerou as contagens antigas da §3.5 não está em
    código, e o desta função chama de "revisão" o que é só atualização de
    nomenclatura (Cambissolo Álico → Cambissolo Háplico Distrófico); separar
    as duas exige correspondência classe a classe entre o sistema anterior e
    o SiBCS. Os números por estrato não devem ir para o texto. Aqui: texto
    igual em conteúdo → não reclassificado; diferente e o original já usa
    nome de ordem do SiBCS → revisão taxonômica; diferente e não usa →
    atualização de nomenclatura.
    """
    o = _comparavel(bruto.get("_class_original"))
    a = _comparavel(bruto.get("_class_atual"))
    if not o or not a:
        return "sem texto"
    if o == a:
        return "não reclassificado"
    return ("revisão taxonômica" if _ORDENS_SIBCS.search(o)
            else "atualização de nomenclatura")


def desfecho(res, ordem: str) -> str:
    alc = set(res.alcancaveis) | ({res.classe} if res.classe else set())
    if res.conclusivo and res.classe == ordem:
        return "concorda"
    if ordem in alc:
        return "contém"
    return "diverge"


def _linha(rotulo, linhas, largura=34):
    n = len(linhas)
    conc = sum(1 for l in linhas if l["desfecho"] == "concorda")
    cont = sum(1 for l in linhas if l["desfecho"] != "diverge")
    grupos = defaultdict(list)
    for l in linhas:
        grupos[l["levantamento"]].append(1 if l["desfecho"] == "concorda" else 0)
    lo, hi = bootstrap_por_grupo(list(grupos.values())) if n else (float("nan"),) * 2
    print(f"{rotulo:<{largura}} {n:>5}  concorda {conc:>5} {fmt(wilson(conc, n))}"
          f"  [lev.: {fmt(lo)}–{fmt(hi)}]  contém/concorda {cont:>5}"
          f"  diverge {n - cont:>4}")
    return {"n": n, "concorda": conc, "wilson": list(wilson(conc, n)),
            "bootstrap_levantamento": [lo, hi], "contem_ou_concorda": cont,
            "diverge": n - cont, "levantamentos": len(grupos)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ablacao", action="store_true",
                    help="também a ablação do Avaliador Parcial (lenta)")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    pares = carregar(1)
    linhas = []
    for bruto, perfil in pares:
        ordem = (bruto.get("ORDEM") or "").upper()
        res = classificar(perfil)
        linhas.append({"id": perfil.id_ponto, "ordem": ordem,
                       "levantamento": levantamento(perfil.id_ponto),
                       "uf": bruto.get("_uf"), "estrato": estrato(bruto),
                       "classe": res.classe, "conclusivo": res.conclusivo,
                       "alcancaveis": sorted(set(res.alcancaveis)),
                       "desfecho": desfecho(res, ordem)})

    saida: dict = {}
    print("Avaliação do núcleo sobre o BDSolos (5ª edição, 1º nível categórico)")
    print("=" * 100)
    print(f"perfis: {len(linhas)} (corroborados, sem os registros do conjunto curado);"
          f" levantamentos: {len({l['levantamento'] for l in linhas})}")
    print("Concordância = o núcleo conclui a ordem registrada. IC de Wilson;"
          " [lev.] = reamostragem por levantamento.\n")
    saida["geral"] = _linha("todos", linhas)
    no_recorte = [l for l in linhas if l["ordem"] in RECORTE]
    saida["recorte"] = _linha("ordens do recorte (Quadro 6)", no_recorte)
    saida["fora_recorte"] = _linha("demais ordens (só triagem)",
                                   [l for l in linhas if l["ordem"] not in RECORTE])

    print("\npor ordem registrada")
    print("-" * 100)
    saida["por_ordem"] = {}
    for ordem in sorted({l["ordem"] for l in linhas},
                        key=lambda o: -sum(1 for l in linhas if l["ordem"] == o)):
        marca = " *" if ordem in RECORTE else ""
        saida["por_ordem"][ordem] = _linha(ordem + marca,
                                           [l for l in linhas if l["ordem"] == ordem])
    print("(* = ordem do recorte)")

    # Divergências: o que o núcleo deriva quando a ordem registrada sai.
    div = [l for l in linhas if l["desfecho"] == "diverge"]
    pares_div = Counter((l["ordem"], l["classe"] or "—") for l in div)
    print(f"\ndivergências: {len(div)} — pares (registrada → derivada), mais frequentes:")
    for (o, c), k in pares_div.most_common(15):
        print(f"   {o:<14} → {c:<14} {k:>4}")
    saida["divergencias"] = {f"{o} -> {c}": k for (o, c), k in pares_div.items()}

    prop = [l for l in linhas if l["conclusivo"] and l["classe"] in RECORTE
            and l["ordem"] in PRECEDENTES and l["ordem"] != l["classe"]]
    print(f"\npropagação pela precedência (§3.5): concluídos numa ordem do recorte"
          f" com rótulo {'/'.join(PRECEDENTES)}: {len(prop)}")
    print(f"   {dict(Counter((l['ordem'], l['classe']) for l in prop).most_common())}")
    saida["propagacao"] = len(prop)

    print("\n⚠️ por estrato de reclassificação — critério RECONSTRUÍDO, exploratório"
          " (não reproduz a §3.5)")
    print("-" * 100)
    saida["por_estrato"] = {}
    for e in ("não reclassificado", "atualização de nomenclatura",
              "revisão taxonômica", "sem texto"):
        sub = [l for l in linhas if l["estrato"] == e]
        if sub:
            saida["por_estrato"][e] = _linha(e, sub)

    if args.ablacao:
        from .avaliacao_parcial import GRUPOS, ablacao, relatorio
        from .explicador import ATRIBUTOS_ANALITICOS, ATRIBUTOS_COR
        perfis = [p for _, p in pares]
        isolados = {a: (a,) for a in ATRIBUTOS_ANALITICOS + ATRIBUTOS_COR}
        print("\nAblação do Avaliador Parcial sobre o BDSolos")
        saida["ablacao_isolado"] = relatorio("Atributo isolado", ablacao(perfis, isolados))
        saida["ablacao_grupo"] = relatorio("Grupo de atributos", ablacao(perfis, GRUPOS))

    print("\nLeitura. Rótulo produzido fora do conjunto curado; a independência em"
          " relação ao sistema de referência\né hipótese (§3.5). Concordância não é"
          " acurácia enquanto essa hipótese não for verificada.")
    if args.json:
        saida["perfis_divergentes"] = [l["id"] for l in div]
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
