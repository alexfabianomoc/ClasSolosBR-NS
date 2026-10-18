"""Linha de comando do núcleo simbólico do ClasSolosBR-NS5.

    python -m nucleo.cli classificar PERFIL.json [--prova] [--falhas]
    python -m nucleo.cli lote DIRETORIO           # concordância por nível 1
    python -m nucleo.cli cotejar PERFIL.json      # as duas edições lado a lado
    python -m nucleo.cli cobertura                # o que está implementado
    python -m nucleo.cli edicoes                  # precedências e assimetrias

A **edição de produção é a 5ª** (SANTOS et al., 2018): é a que o sistema de
referência implementa e sob a qual os dois acervos foram rotulados. Use
`--edicao 6` para rodar sob a 6ª, ou `cotejar` para as duas ao mesmo tempo.

⚠️ No modo `lote`, o rótulo do PYKKA7 é da 5ª edição. Sob `--edicao 5` a
concordância mede implementação; sob `--edicao 6`, mede diferença de norma
somada à implementação, e divergência em Espodossolos é esperada — é o que a
camada versão-consciente existe para diagnosticar. O relatório separa as duas
situações.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

from .avaliador import classificar
from .chave5 import cobertura as cobertura5
from .chave6 import cobertura as cobertura6
from .edicoes import (
    EDICAO_PADRAO, ROTULO, assimetrias, chave_de, cotejar, precedencias,
)
from .perfil import carregar_json

#: Ordens cuja classe pode mudar entre a 5ª e a 6ª edição por reestruturação.
#: Divergência aqui é resultado, não defeito.
REESTRUTURADAS = {"ESPODOSSOLO"}


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").upper())
        if unicodedata.category(c) != "Mn"
    )


def _classificar(args) -> int:
    chave = chave_de(args.edicao)
    for perfil in carregar_json(args.arquivo):
        resultado = classificar(perfil, chave)
        registrado = perfil.classe_registrada[0] or "—"
        print(f"\n{perfil.id_ponto}")
        print(f"  horizontes : {' '.join(h.simbolo for h in perfil.horizontes)}")
        print(f"  registrado : {registrado}  (5ª ed.)")
        print(f"  derivado   : {resultado.resumo()}  ({ROTULO[args.edicao]})")
        if resultado.pendencias:
            print("  pendências :")
            for p in dict.fromkeys(resultado.pendencias):
                print(f"    · {p}")
        if args.prova and resultado.derivacao:
            print("\n  árvore de prova:")
            print("\n".join("    " + l for l in
                            resultado.derivacao.texto().splitlines()))
        if args.falhas:
            print("\n  pontos de ruptura das classes refutadas:")
            for classe, derivacao in resultado.refutadas:
                for folha in derivacao.folhas_falhas():
                    extra = (f"  [falta {folha.distancia:g}]"
                             if folha.distancia is not None else "")
                    print(f"    {classe}: {folha.rotulo} — {folha.detalhe}{extra}")
    return 0


def _cotejar(args) -> int:
    """Módulo versão-consciente (M3) sobre um arquivo de perfis."""
    for perfil in carregar_json(args.arquivo):
        c = cotejar(perfil)
        registrado = perfil.classe_registrada[0] or None
        print(f"\n{perfil.id_ponto}")
        print(f"  horizontes : {' '.join(h.simbolo for h in perfil.horizontes)}")
        print(f"  registrado : {registrado or '—'}")
        print(f"  5ª edição  : {c.sob_5a.resumo()}")
        print(f"  6ª edição  : {c.sob_6a.resumo()}")
        print(f"  diagnóstico: {c.diagnostico(registrado)}")
    return 0


def _lote(args) -> int:
    arquivos = sorted(Path(args.diretorio).rglob("*.json"))
    arquivos = [a for a in arquivos if not a.name.endswith("_all.json")]
    if not arquivos:
        print(f"nenhum .json em {args.diretorio}", file=sys.stderr)
        return 2

    chave = chave_de(args.edicao)
    iguais = divergentes = reestruturadas = indeterminados = 0
    linhas: list[str] = []
    for arquivo in arquivos:
        for perfil in carregar_json(arquivo):
            resultado = classificar(perfil, chave)
            registrado = _sem_acento(perfil.classe_registrada[0] or "")
            derivado = _sem_acento(resultado.classe or "")
            if not resultado.conclusivo:
                indeterminados += 1
                estado = "indeterminado"
            elif derivado == registrado:
                iguais += 1
                estado = "igual"
            elif args.edicao != "5" and (registrado in REESTRUTURADAS
                                         or derivado in REESTRUTURADAS):
                reestruturadas += 1
                estado = "divergência de edição (esperada)"
            else:
                divergentes += 1
                estado = "divergente"
            if estado != "igual" or args.tudo:
                linhas.append(
                    f"  {perfil.id_ponto:34} {registrado or '—':14} → "
                    f"{resultado.resumo():48} [{estado}]"
                )

    total = iguais + divergentes + reestruturadas + indeterminados
    print("\n".join(linhas))
    print(f"\n{total} perfis sob {ROTULO[args.edicao]}")
    print(f"  concordância no 1º nível      : {iguais:4}  "
          f"({100 * iguais / total:.1f}%)")
    if args.edicao != "5":
        print(f"  divergência de edição esperada: {reestruturadas:4}")
    print(f"  não conclusivos               : {indeterminados:4}")
    print(f"  divergentes a investigar      : {divergentes:4}")
    if args.edicao == "5":
        print("\nRótulo de referência e núcleo são da mesma edição: aqui a "
              "concordância mede implementação.")
    else:
        print("\n⚠️ Rótulo de referência é 5ª edição e o núcleo é 6ª. "
              "Concordância não é acurácia — é conformidade entre edições "
              "diferentes.")
    return 0


def _cobertura(args) -> int:
    print(f"### {ROTULO[args.edicao]}")
    print(cobertura5() if args.edicao == "5" else cobertura6())
    return 0


def _edicoes(_args) -> int:
    print("### Precedência das ordens\n")
    print("| # | 5ª ed. (produção) | 6ª ed. (contraprova) |")
    print("|---|---|---|")
    for pos, c5, _, c6 in precedencias():
        marca = "" if c5 == c6 else "  ←"
        print(f"| {pos} | {c5} | {c6}{marca} |")
    print("\n### Diferenças entre as bases\n")
    print("Cada linha deve corresponder a uma diferença **entre as edições**. "
          "Linhas marcadas com ⚠️ são assimetrias de modelagem e devem ser "
          "corrigidas ou justificadas.\n")
    for a in assimetrias():
        print(f"- {a}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="nucleo", description=__doc__)
    parser.add_argument("--edicao", choices=sorted(ROTULO), default=EDICAO_PADRAO,
                        help="edição do SiBCS a usar (padrão: %(default)s)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p1 = sub.add_parser("classificar", help="classifica um arquivo de perfis")
    p1.add_argument("arquivo")
    p1.add_argument("--prova", action="store_true", help="mostra a árvore de prova")
    p1.add_argument("--falhas", action="store_true",
                    help="mostra os pontos de ruptura das classes refutadas")
    p1.set_defaults(func=_classificar)

    p2 = sub.add_parser("lote", help="roda sobre um diretório de perfis")
    p2.add_argument("diretorio")
    p2.add_argument("--tudo", action="store_true", help="lista também os iguais")
    p2.set_defaults(func=_lote)

    p3 = sub.add_parser("cotejar", help="as duas edições lado a lado (M3)")
    p3.add_argument("arquivo")
    p3.set_defaults(func=_cotejar)

    p4 = sub.add_parser("cobertura", help="o que está implementado")
    p4.set_defaults(func=_cobertura)

    p5 = sub.add_parser("edicoes", help="precedências e diferenças entre as bases")
    p5.set_defaults(func=_edicoes)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
