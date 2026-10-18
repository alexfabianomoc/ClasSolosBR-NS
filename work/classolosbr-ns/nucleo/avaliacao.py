"""Avaliação do conjunto PYKKA7 estratificada pela existência da ficha curada.

    python -m nucleo.avaliacao

✅ **O rótulo do PYKKA7 e a base de produção são ambos da 5ª edição do
SiBCS** (desde 2026-09-11). A edição do rótulo está declarada pelos autores no
`README-ptBR.md` do próprio conjunto:

    linha 171: "A classificação de solo é baseada apenas na 5a versão do SiBCS."
    linha 180: "O conjunto de dados inclui atributos de classificação para a
                5a edição do SiBCS. Portanto, não deve ser usado se uma outra
                versão do SiBCS precisar ser considerada."

O conjunto foi depositado em 2023-09-19 e publicado em 2023-10-20; a 6ª edição
é de 2025. Logo, `"Nenhuma alteração."` **não** significa "não mudou da 5ª para
a 6ª edição": significa que a ficha daquele perfil não precisou de correção
quando foi conferida contra a 5ª. A defasagem que a curadoria tratou foi de
edições **anteriores** para a 5ª.

A consequência para esta avaliação é direta: **concordância ainda não é
acurácia**, mas por **uma** razão a menos que antes. Com rótulo e núcleo na
mesma edição, a mudança normativa deixa de explicar divergência: sobram o erro
do núcleo e a limitação declarada do recorte. O que impede ler o número como
acurácia é a **circularidade** — o rótulo foi curado com auxílio do próprio
sistema de referência. Rode com `--edicao 6` para o cotejo entre edições.

**Critério de estrato (2026-10-11): a existência da ficha curada.** Um perfil
está em "com correção" se o conjunto traz, em `<UF>/updated/`, a ficha
atualizada pelos curadores — o README do PYKKA7 diz que ela existe "caso este
seja diferente do original". São **62 com correção e 32 sem alteração**.

O critério anterior era textual — `CURADORIA` começando por "nenhuma altera" —
e dava 27/67. Ele punha em "com correção" cinco perfis sem ficha curada: três
que dizem não ter havido mudança com outra redação (`PE_015` "Sem
alterações.", `RN_033` "Nenhum alteração.", `RN_016` "."), e dois cuja
mudança foi só de transcrição para o JSON, não da ficha (`PE_004`, Ca e Mg
somados divididos ao meio; `RN_021`, `FLUVICO = true`). O estrato "sem
alteração" mede, assim, as fichas que o especialista não precisou corrigir —
ainda que a transcrição para o contrato tenha exigido decisões.
Ver `[[curadoria-explicada-de-dados-de-solo]]`.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from pathlib import Path

from .avaliador import classificar
from .edicoes import EDICAO_PADRAO, ROTULO, chave_de
from .perfil import carregar_json

PYKKA7 = Path(__file__).resolve().parents[3] / "raw" / "pykka7-smartsolos-dataset"

#: Ordens reestruturadas entre a 5ª e a 6ª edição. Divergência aqui é
#: resultado esperado, e não defeito — a 6ª extinguiu as subordens da 5ª.
REESTRUTURADAS = {"ESPODOSSOLO"}

#: Ordens implementadas a fundo. Fora delas a regra é de triagem, e o
#: indeterminado é o comportamento correto, não uma falha.
def _recorte(chave):
    return {r.classe for r in chave if r.no_recorte}


def _limpo(texto: str | None) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").upper())
        if unicodedata.category(c) != "Mn"
    ).strip()


def _bruto(caminho: Path) -> dict:
    import json
    return json.JSONDecoder().raw_decode(
        caminho.read_text(encoding="utf-8"))[0]["items"][0]


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="nucleo.avaliacao", description=__doc__)
    p.add_argument("--edicao", choices=sorted(ROTULO), default=EDICAO_PADRAO,
                   help="edicao do SiBCS a usar (padrao: %(default)s)")
    args = p.parse_args(argv)
    chave = chave_de(args.edicao)
    RECORTE = _recorte(chave)

    arquivos = [a for a in sorted(PYKKA7.rglob("*.json"))
                if not a.name.endswith("_all.json")]

    estratos: dict[str, list] = {"sem alteração": [], "com correção": []}
    for arquivo in arquivos:
        item = _bruto(arquivo)
        curadoria = (item.get("CURADORIA") or item.get("CURADORIA_AUTOR") or "").strip()
        # O perfil foi corrigido se os curadores publicaram uma ficha
        # atualizada distinta da original. Ver a docstring do módulo.
        ficha_curada = arquivo.parent.parent / "updated" / (arquivo.stem + ".rtf")
        estrato = "com correção" if ficha_curada.exists() else "sem alteração"
        perfil = carregar_json(arquivo)[0]
        estratos[estrato].append((perfil, classificar(perfil, chave), curadoria))

    print(__doc__.split("\n\n")[0])
    print(f"\nconjunto: {sum(len(v) for v in estratos.values())} perfis em "
          f"{len(arquivos)} arquivos\n")

    for nome, itens in estratos.items():
        print(f"{'='*72}\n{nome.upper()} — {len(itens)} perfis\n{'='*72}")
        contagem = Counter()
        divergentes = []
        for perfil, resultado, _ in itens:
            registrado = _limpo(perfil.classe_registrada[0])
            derivado = _limpo(resultado.classe)
            possiveis = {_limpo(c) for c in resultado.alcancaveis} | {derivado}

            if registrado == "UNKNOWN":
                estado = "rótulo é 'unknown' na origem"
            elif not resultado.conclusivo:
                estado = ("indeterminado, contém o rótulo"
                          if registrado in possiveis
                          else "indeterminado, NÃO contém o rótulo")
            elif derivado == registrado:
                estado = "concorda"
            elif registrado in REESTRUTURADAS or derivado in REESTRUTURADAS:
                estado = "divergência de edição (esperada)"
            elif registrado not in RECORTE:
                estado = "divergente — rótulo fora do recorte implementado"
            else:
                estado = "DIVERGENTE dentro do recorte"
            contagem[estado] += 1
            if estado.startswith(("DIVERGENTE", "indeterminado, NÃO")):
                divergentes.append((perfil.id_ponto, registrado, resultado.resumo()))

        for estado, n in contagem.most_common():
            print(f"  {n:3}  {estado}")
        if divergentes:
            print("\n  a investigar:")
            for pid, reg, res in divergentes:
                print(f"    {pid:34} {reg:12} → {res}")
        print()

    print("=" * 72)
    print("Leitura. A soma 'concorda' + 'indeterminado, contém o rótulo' é a")
    print("medida de **contenção**: em quantos perfis a classe registrada")
    print("sobrevive à avaliação. É a única linha que mede o núcleo sem")
    print("confundir defeito com diferença de edição ou com o recorte.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
