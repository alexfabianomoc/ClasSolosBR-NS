"""Concordância por nível categórico (escala L0–L4) — conjunto curado e BDSolos.

    python -m nucleo.avaliacao_niveis [--bdsolos] [--json SAIDA.json]

Escala da §3.4 (L0 a L4): cada
perfil cai na faixa do nível mais profundo em que a classe inferida e a
registrada ainda coincidem — L0 quando divergem na ordem, L1 quando
coincidem só na ordem, até L4. Um nível só conta como coincidente quando o
núcleo **conclui** nele; "não conclui" é registrado à parte, porque não é
discordância.

Só entram, em cada nível k, os perfis com rótulo até k e com ordem do recorte
(as outras oito ordens não têm 2º e 3º níveis formalizados). Conjunto
curado: os rótulos do JSON (5ª ed.). BDSolos: os do adaptador, corroborados
e sem os registros que repetem o conjunto curado, com reamostragem por
levantamento.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .avaliacao import PYKKA7
from .estatistica import bootstrap_por_grupo, fmt, wilson
from .niveis5 import (GRANDES_GRUPOS, SUBORDENS, classificar_niveis, coincide,
                      normaliza)
from .perfil import carregar_json

CAMPOS = ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")


def desfecho_niveis(rotulo: list[str], resultados) -> tuple[int, str]:
    """(faixa L, motivo da parada) — L é o nível mais profundo que coincide."""
    faixa = 0
    for k, (esperado, res) in enumerate(zip(rotulo, resultados), start=1):
        if not esperado:
            return faixa, "sem rótulo"
        if res is None:
            return faixa, "nível não avaliado (acima não concluiu)"
        if not res.conclusivo:
            alc = set(res.alcancaveis) | ({res.classe} if res.classe else set())
            contem = any(coincide(esperado, c) for c in alc)
            return faixa, ("não conclui, rótulo alcançável" if contem
                           else "não conclui, rótulo fora")
        if not coincide(esperado, res.classe):
            return faixa, "diverge"
        faixa = k
    return faixa, "coincide até o 4º nível"


def relatorio(nome, casos, grupo_de=None) -> dict:
    """casos: lista de (id, rotulo[3], resultados[3], grupo)."""
    print(f"\n{nome}")
    print("-" * 78)
    saida = {}
    for k in (1, 2, 3, 4):
        elegiveis = [c for c in casos
                     if all(c[1][:k]) and normaliza(c[1][0]) in {normaliza(o) for o in SUBORDENS}]
        if not elegiveis:
            continue
        coincide = [c for c in elegiveis if desfecho_niveis(c[1], c[2])[0] >= k]
        motivos = Counter(desfecho_niveis(c[1][:k], c[2][:k])[1] for c in elegiveis
                          if desfecho_niveis(c[1], c[2])[0] < k)
        n, a = len(elegiveis), len(coincide)
        linha = f"nível {k}: {a}/{n} coincidem até o nível {k}  {fmt(wilson(a, n))}"
        if grupo_de:
            grupos = defaultdict(list)
            for c in elegiveis:
                grupos[grupo_de(c[0])].append(1 if c in coincide else 0)
            lo, hi = bootstrap_por_grupo(list(grupos.values()))
            linha += f"  [lev.: {fmt(lo)}–{fmt(hi)}]"
        print(linha)
        print(f"         onde para: {dict(motivos)}")
        saida[f"nivel_{k}"] = {"n": n, "coincide": a, "motivos": dict(motivos)}
    faixas = Counter(desfecho_niveis(c[1], c[2])[0] for c in casos
                     if normaliza(c[1][0]) in {normaliza(o) for o in SUBORDENS})
    print(f"faixas L (perfis das cinco ordens): {dict(sorted(faixas.items()))}")
    saida["faixas"] = dict(faixas)
    return saida


def casos_curados():
    casos = []
    for f in sorted(PYKKA7.rglob("*.json")):
        if f.name.endswith("_all.json"):
            continue
        bruto, _ = json.JSONDecoder().raw_decode(f.read_text(encoding="utf-8"))
        item = bruto["items"][0]
        perfil = carregar_json(f)[0]
        rotulo = [item.get(c) for c in CAMPOS]
        casos.append((perfil.id_ponto, rotulo, classificar_niveis(perfil), None))
    return casos


def casos_bdsolos():
    from .avaliacao_bdsolos import carregar
    casos = []
    for bruto, perfil in carregar(1):
        rotulo = [bruto.get(c) for c in CAMPOS]
        casos.append((perfil.id_ponto, rotulo, classificar_niveis(perfil), None))
    return casos


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bdsolos", action="store_true")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    print("Concordância por nível categórico, escala L0–L4 (SiBCS 5ª ed.)")
    print("=" * 78)
    from .niveis5_subgrupos import SUBGRUPOS
    print(f"regras: {sum(len(v) for v in SUBORDENS.values())} subordens, "
          f"{sum(len(v) for v in GRANDES_GRUPOS.values())} grandes grupos, "
          f"{sum(len(v) for v in SUBGRUPOS.values())} subgrupos, "
          f"nas ordens {', '.join(SUBORDENS)}")
    saida = {"curado": relatorio("Conjunto curado (94 perfis) — conformidade",
                                 casos_curados())}
    if args.bdsolos:
        saida["bdsolos"] = relatorio(
            "BDSolos (corroborados, sem os do conjunto curado) — verificação fora da amostra",
            casos_bdsolos(), grupo_de=lambda i: i.split("|")[1])
    if args.json:
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
