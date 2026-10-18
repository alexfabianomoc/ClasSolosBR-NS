#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linha de base × núcleo, nível a nível, nos mesmos perfis (ordens do recorte).

    python tools/linha_base_niveis.py

Para cada conjunto (curado e acervo nacional) e cada nível n, entram os perfis
com rótulo até n, ordem registrada numa das cinco do recorte e resposta do
sistema de referência (SR) no cache de `linha_base.py`. Conta-se:

* SR: faixa L (contra o rótulo enviado, "unknown" nunca concorda) >= n;
* núcleo: coincide até o nível n (`nucleo.avaliacao_niveis.desfecho_niveis`).

Os dois sobre o **mesmo** denominador, com intervalo de Wilson e, no acervo,
reamostragem por levantamento. Sem rede: só lê o cache.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "work" / "classolosbr-ns"))
import linha_base as L  # noqa: E402
from nucleo.avaliacao_niveis import CAMPOS, casos_bdsolos, casos_curados, desfecho_niveis  # noqa: E402
from nucleo.estatistica import bootstrap_por_grupo, fmt, wilson  # noqa: E402
from nucleo.niveis5 import SUBORDENS, normaliza  # noqa: E402

RECORTE = {normaliza(o) for o in SUBORDENS}


def apura(nome, casos, cache, prefixo, grupo_de=None):
    print(f"\n=== {nome}")
    for n in (1, 2, 3, 4):
        linhas = []
        for pid, rotulo, resultados, _ in casos:
            if not all(rotulo[:n]) or normaliza(rotulo[0]) not in RECORTE:
                continue
            r = cache["respostas"].get(f"{prefixo}|{pid}")
            if not r:
                continue
            rot = dict(zip(CAMPOS, rotulo))
            sr = L.faixa(r["inferido"] or {}, rot) >= n
            nuc = desfecho_niveis(rotulo, resultados)[0] >= n
            linhas.append((pid, sr, nuc))
        tot = len(linhas)
        k_sr = sum(1 for x in linhas if x[1])
        k_nuc = sum(1 for x in linhas if x[2])
        ambos = sum(1 for x in linhas if x[1] and x[2])
        extra = ""
        if grupo_de:
            for rot_, i in (("SR", 1), ("núcleo", 2)):
                g = defaultdict(list)
                for x in linhas:
                    g[grupo_de(x[0])].append(1 if x[i] else 0)
                lo, hi = bootstrap_por_grupo(list(g.values()))
                extra += f"  [lev. {rot_}: {fmt(lo)}–{fmt(hi)}]"
        print(f"nível {n}: {tot} perfis | SR {k_sr} {fmt(wilson(k_sr, tot))} | "
              f"núcleo {k_nuc} {fmt(wilson(k_nuc, tot))} | os dois {ambos}{extra}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cache = L._carrega_cache()
    apura("Conjunto curado (conformidade)", casos_curados(), cache, "curado")
    apura("Acervo nacional (fora da amostra)", casos_bdsolos(), cache, "bdsolos",
          grupo_de=lambda i: i.split("|")[1])


if __name__ == "__main__":
    main()
