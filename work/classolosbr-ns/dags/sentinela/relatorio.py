"""Aplica a gramática de sufixos a um corpus e resume os achados.

Sem Spark e sem Airflow de propósito: os dois corpora cabem na memória, e o
relatório precisa rodar também fora do contêiner — na defesa, num notebook, ou
para conferir um número citado na monografia.

    python -m sentinela.relatorio bdsolos
    python -m sentinela.relatorio pykka7 --edicao 2015
    python -m sentinela.relatorio bdsolos --detalhar NOTACAO_LEGADA

⚠️ Números medidos, não estimados. Divergência significa que a fonte mudou ou
que a gramática mudou — nos dois casos é para alguém olhar.
"""

from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import os
import sys
from collections import Counter, defaultdict

from sentinela.gramatica_sufixos import (
    EDICAO_PADRAO,
    moderniza,
    suspeita_k_barra_perdido,
    valida,
)

# O wiki é a fonte imutável; o contêiner a monta em /opt/airflow/raw:ro.
RAW = os.environ.get("CLASSOLOSBR_RAW") or os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "raw")

GRAVIDADES = ("erro", "alerta", "suspeita", "nota")


def _num(valor) -> float | None:
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def carrega_pykka7() -> list[tuple[str, float | None]]:
    padrao = os.path.join(RAW, "pykka7-smartsolos-dataset", "*", "json",
                          "GeoTab_*_all.json")
    pares: list[tuple[str, float | None]] = []
    for caminho in sorted(glob.glob(padrao)):
        with io.open(caminho, encoding="utf-8") as fh:
            dados = json.load(fh)
        for item in dados.get("items", []):
            for horizonte in item.get("HORIZONTES") or []:
                simbolo = (horizonte.get("SIMB_HORIZ") or "").strip()
                if simbolo:
                    pares.append((simbolo, _num(horizonte.get("EQUI_CACO3"))))
    return pares


def carrega_bdsolos() -> list[tuple[str, float | None]]:
    caminho = os.path.join(RAW, "bd_solos_para_redape.csv")
    csv.field_size_limit(10 ** 7)
    pares: list[tuple[str, float | None]] = []
    with io.open(caminho, encoding="utf-8", errors="replace", newline="") as fh:
        # ⚠️ Delimitador é ponto e vírgula. Com a vírgula padrão o arquivo lê
        # 106.166 "horizontes" em vez de 33.327 — e tudo a jusante fica errado.
        leitor = csv.DictReader(fh, delimiter=";")
        col_simbolo = _acha(leitor.fieldnames, "Símbolo Horizonte")
        col_caco3 = _acha(leitor.fieldnames, "Equivalente de Carbonato")
        for linha in leitor:
            simbolo = (linha.get(col_simbolo) or "").strip()
            if simbolo:
                pares.append((simbolo, _num(linha.get(col_caco3))))
    return pares


def _acha(colunas, trecho: str) -> str:
    for coluna in colunas or []:
        if coluna and trecho in coluna:
            return coluna
    raise SystemExit(f"coluna contendo {trecho!r} não encontrada no CSV")


CORPORA = {"pykka7": carrega_pykka7, "bdsolos": carrega_bdsolos}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corpus", choices=sorted(CORPORA))
    ap.add_argument("--edicao", default=EDICAO_PADRAO,
                    help="edição da norma contra a qual validar")
    ap.add_argument("--detalhar", metavar="CODIGO",
                    help="lista os símbolos distintos que geraram este código")
    ap.add_argument("--limite", type=int, default=20)
    args = ap.parse_args(argv)

    pares = CORPORA[args.corpus]()
    if not pares:
        print(f"nenhum horizonte lido em {args.corpus}", file=sys.stderr)
        return 1

    contagem: Counter = Counter()
    exemplo: dict[tuple[str, str], str] = {}
    por_codigo: defaultdict[str, Counter] = defaultdict(Counter)
    conformes = com_erro = 0

    for simbolo, caco3 in pares:
        achados = valida(simbolo, args.edicao)
        suspeita = suspeita_k_barra_perdido(simbolo, caco3)
        if suspeita:
            achados = achados + [suspeita]
        if not achados:
            conformes += 1
        if any(a.gravidade == "erro" for a in achados):
            com_erro += 1
        for achado in achados:
            chave = (achado.gravidade, achado.codigo)
            contagem[chave] += 1
            exemplo.setdefault(chave, simbolo)
            por_codigo[achado.codigo][simbolo] += 1

    total = len(pares)
    distintos = len({s for s, _ in pares})
    print(f"{args.corpus} · edição {args.edicao} · {total} horizontes · "
          f"{distintos} símbolos distintos")
    print("-" * 78)
    ordem = {g: i for i, g in enumerate(GRAVIDADES)}
    for (gravidade, codigo), n in sorted(
            contagem.items(), key=lambda x: (ordem[x[0][0]], -x[1])):
        print(f"  {gravidade:<9}{codigo:<26}{n:>6}  ({100 * n / total:5.1f}%)"
              f"  ex: {exemplo[(gravidade, codigo)]}")
    print("-" * 78)
    print(f"  conformes: {conformes} ({100 * conformes / total:.1f}%)"
          f"   ·   com erro: {com_erro} ({100 * com_erro / total:.1f}%)")

    if args.detalhar:
        print(f"\nsímbolos distintos em {args.detalhar} "
              f"(top {args.limite}):")
        for simbolo, n in por_codigo[args.detalhar].most_common(args.limite):
            sugestao = moderniza(simbolo)
            seta = f"  →  {sugestao}" if sugestao else ""
            print(f"  {n:>5}  {simbolo}{seta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
