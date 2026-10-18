"""Conversão mínima de RTF para texto — só biblioteca padrão.

    python -m transcricao.rtf_texto FICHA.rtf

Serve à transcrição das fichas originais do conjunto curado (monografia,
§3.4: "os atributos das fichas originais precisam ser transcritos para o
formato de entrada"). Não pretende ser um leitor de RTF completo: descarta os
grupos de cabeçalho (fontes, cores, estilos, metadados, imagens), traduz os
escapes de caractere e converte a estrutura de tabela em texto tabulado —
célula → tabulação, linha → quebra de linha —, porque os dados analíticos das
fichas vêm em tabela.

O que ela não faz, e por que não precisa: formatação (negrito, itálico,
tamanho) é descartada. ⚠️ O itálico carrega significado em alguns símbolos de
horizonte (seção 2.4 da monografia); quem transcreve símbolo deve conferir na
ficha, não confiar neste texto para isso.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: Destinos cujo conteúdo não é texto do documento.
_IGNORAR = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "themedata",
    "colorschememapping", "latentstyles", "datastore", "xmlnstbl", "listtable",
    "listoverridetable", "rsidtbl", "generator", "mmathPr", "header", "footer",
    "headerl", "headerr", "footerl", "footerr", "fldinst", "object", "shp",
    "shppict", "nonshppict", "pgdsctbl", "filetbl", "revtbl", "wgrffmtfilter",
    "defchp", "defpap", "pnseclvl", "bkmkstart", "bkmkend",
}

_TOKEN = re.compile(
    r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|([^\\{}\r\n]+)|[\r\n]+")


def para_texto(rtf: str) -> str:
    pilha: list[tuple[bool, int]] = []
    ignorar, uc = False, 1
    pular = 0          # caracteres de reserva após \uN
    saida: list[str] = []
    asterisco = False
    for m in _TOKEN.finditer(rtf):
        palavra, num, hexa, simbolo, chave, texto = m.groups()
        if chave == "{":
            pilha.append((ignorar, uc))
            asterisco = False
            continue
        if chave == "}":
            if pilha:
                ignorar, uc = pilha.pop()
            continue
        if palavra:
            if palavra in _IGNORAR or asterisco:
                ignorar = True
                asterisco = False
                continue
            if ignorar:
                continue
            if palavra == "uc":
                uc = int(num or 1)
            elif palavra == "u":
                n = int(num)
                saida.append(chr(n + 65536 if n < 0 else n))
                pular = uc
            elif palavra in ("par", "line", "sect", "page"):
                saida.append("\n")
            elif palavra == "row":
                saida.append("\n")
            elif palavra in ("cell", "nestcell"):
                saida.append("\t")
            elif palavra == "tab":
                saida.append(" ")
            continue
        if simbolo is not None:
            if simbolo == "*":
                asterisco = True
            elif not ignorar and simbolo in "\\{}":
                saida.append(simbolo)
            elif not ignorar and simbolo == "~":
                saida.append(" ")
            continue
        if ignorar:
            continue
        if hexa:
            if pular:
                pular -= 1
                continue
            saida.append(bytes([int(hexa, 16)]).decode("cp1252", errors="replace"))
            continue
        if texto:
            if pular:
                corte = min(pular, len(texto))
                texto = texto[corte:]
                pular -= corte
            saida.append(texto)
    texto = "".join(saida)
    texto = re.sub(r"[ \u00a0]+\n", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def ler(caminho: str | Path) -> str:
    return para_texto(Path(caminho).read_bytes().decode("latin-1"))


if __name__ == "__main__":  # pragma: no cover
    sys.stdout.reconfigure(encoding="utf-8")
    print(ler(sys.argv[1]))
