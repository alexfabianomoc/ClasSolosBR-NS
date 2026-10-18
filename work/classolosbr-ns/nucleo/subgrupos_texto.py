"""Extração do texto dos subgrupos (4º nível) da 5ª edição, a partir do PDF.

    python -m nucleo.subgrupos_texto PDF_EM_TEXTO.txt [--saida dados/subgrupos5.json]

O texto do PDF (`pdftotext -enc UTF-8 -layout`) é cortado nos cinco capítulos
do recorte, e cada entrada numerada de três níveis ("3.4.1 ARGISSOLOS
AMARELOS Distróficos abrúpticos") vira um registro com o grande grupo, o
nome do subgrupo, o texto da definição e a página **impressa** (a do PDF + 2,
conferido no cabeçalho das páginas em 2026-10-15).

O registro é o insumo de `niveis5_subgrupos.py`, que traduz cada
**definição distinta** em condição uma única vez. Guardar o texto ao lado da
regra é o que mantém a base legível contra a norma.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

#: Capítulo → (primeira, última) página **do PDF**.
CAPITULOS = {
    "ARGISSOLO": (113, 136), "CAMBISSOLO": (137, 154),
    "ESPODOSSOLO": (163, 172), "LATOSSOLO": (193, 210), "LUVISSOLO": (211, 216),
}

_ENTRADA = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\s+(.+?)\s*$")
_GG = re.compile(r"^\s*(\d+)\.(\d+)\s+(.+?)\s*$")
_RODAPE = re.compile(r"^\s*(\d{1,3}\s+Sistema Brasileiro|Capítulo \d+\.)")


def extrair(texto_pdf: str) -> list[dict]:
    paginas = texto_pdf.split("\f")
    registros = []
    for ordem, (a, b) in CAPITULOS.items():
        linhas = []
        for i in range(a - 1, b):
            for linha in paginas[i].split("\n"):
                linhas.append((i + 3, linha))
        inicio = next(k for k, (_, l) in enumerate(linhas) if "4º nível" in l)
        atual = None
        gg = None
        for pagina, linha in linhas[inicio + 1:]:
            if _RODAPE.match(linha) or not linha.strip():
                continue
            if re.match(r"^\s*\d+ [A-Z][a-zçãõé]", linha) and atual is None:
                continue  # nota de rodapé
            m = _ENTRADA.match(linha)
            if m:
                if atual:
                    registros.append(atual)
                atual = {"ordem": ordem, "numero": ".".join(m.group(1, 2, 3)),
                         "nome": m.group(4), "texto": "", "pagina": pagina,
                         "grande_grupo": gg}
                continue
            m = _GG.match(linha)
            if m and m.group(3).isupper() is False and m.group(3).split()[0].isupper():
                if atual:
                    registros.append(atual)
                    atual = None
                gg = m.group(3)
                continue
            if atual is not None:
                if re.match(r"^\s*\d+ [A-Z]", linha) and len(linha.strip()) > 40 \
                        and not linha.startswith("     "):
                    continue  # nota de rodapé no meio
                atual["texto"] += " " + linha.strip()
        if atual:
            registros.append(atual)
    for r in registros:
        t = re.sub(r"\s+", " ", r["texto"]).strip()
        t = re.sub(r"(\w)- (\w)", r"\1\2", t)
        t = re.sub(r"\s*\((?:[A-Z][^()]*\d{4}[^()]*)\)\.?$", ".", t)  # citação de perfil-exemplo
        r["texto"] = t
        r["definicao"] = normaliza_definicao(t)
    return registros


def normaliza_definicao(texto: str) -> str:
    """Chave da definição: sem citações de perfil, espaços e pontuação final."""
    t = re.sub(r"\([^()]*(?:\d{4}|perfil)[^()]*\)", "", texto)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".").strip()
    return t


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    argv = argv or sys.argv[1:]
    fonte = Path(argv[0])
    saida = Path(argv[argv.index("--saida") + 1]) if "--saida" in argv else None
    regs = extrair(fonte.read_text(encoding="utf-8"))
    distintas = {}
    for r in regs:
        distintas.setdefault(r["definicao"], []).append(r["nome"])
    print(f"subgrupos: {len(regs)}; definições distintas: {len(distintas)}")
    por_ordem = {}
    for r in regs:
        por_ordem[r["ordem"]] = por_ordem.get(r["ordem"], 0) + 1
    print(por_ordem)
    if saida:
        saida.write_text(json.dumps(regs, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
