#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Discordâncias efetivas entre o núcleo e o sistema de referência (1º nível, recorte).

    python tools/linha_base_discordancias.py [--amostra N] [--json SAIDA]

Discordância efetiva: o núcleo conclui ordem diferente da do sistema de
referência (SR), ou não conclui e a ordem do SR fica fora do conjunto
alcançável. Para cada perfil:

* ordem do SR, ordem registrada e resultado do núcleo;
* **mecanismo**: se a ordem do SR vem antes da concluída pelo núcleo na
  chave da 5ª, o núcleo a **refutou** — registra-se o ponto de ruptura (folha
  falsa da árvore de falha); se vem depois, o núcleo **afirmou** uma ordem que
  o SR não afirma, e a precedência impediu o SR de chegar a ela — registra-se
  a ordem afirmada.
A amostra (semente fixa) é a que se lê à mão.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "work" / "classolosbr-ns"))
import linha_base as L  # noqa: E402
from nucleo.avaliacao import _recorte  # noqa: E402
from nucleo.avaliador import classificar  # noqa: E402
from nucleo.chave5 import CHAVE_5ED  # noqa: E402
from nucleo.perfil import de_dicionario  # noqa: E402

ORDEM_CHAVE = [L.norm(r.classe) for r in CHAVE_5ED]


def rupturas(resultado, classe):
    for c, d in resultado.refutadas:
        if L.norm(c) == classe:
            return [f"{f.rotulo} — {f.detalhe}" for f in d.folhas_falhas()]
    return []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--amostra", type=int, default=0)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    recorte = {L.norm(x) for x in _recorte(CHAVE_5ED)}
    cache = L._carrega_cache()
    casos = []
    for p in L.conjuntos()["bdsolos"]:
        r = cache["respostas"].get(f"bdsolos|{p['ID_PONTO']}")
        if not r:
            continue
        rot = L.norm(p.get("ORDEM"))
        sr = L.norm((r["inferido"] or {}).get("ORDEM"))
        if rot not in recorte or sr in ("", "UNKNOWN"):
            continue
        perfil = de_dicionario(p)
        nuc = classificar(perfil, CHAVE_5ED)
        alc = {L.norm(x) for x in nuc.alcancaveis} | ({L.norm(nuc.classe)} if nuc.classe else set())
        conclusivo = bool(nuc.classe) and not nuc.alcancaveis
        nc = L.norm(nuc.classe) if conclusivo else None
        if nc == sr or (nc is None and sr in alc):
            continue
        if nc is not None and ORDEM_CHAVE.index(sr) > ORDEM_CHAVE.index(nc):
            mecanismo = f"núcleo afirma {nc}, que precede {sr}"
            detalhe = []
        else:
            folhas = rupturas(nuc, sr)
            mecanismo = f"núcleo refuta {sr}: " + (folhas[0].split(" — ")[0] if folhas else "?")
            detalhe = folhas
        casos.append({"id": p["ID_PONTO"], "rotulo": rot, "sr": sr, "nucleo": nc or "não conclui",
                      "alcancaveis": sorted(alc), "mecanismo": mecanismo, "rupturas": detalhe,
                      "horizontes": [h.simbolo for h in perfil.horizontes],
                      "sr_acerta": sr == rot, "nucleo_acerta": nc == rot})
    print(f"discordâncias efetivas no recorte: {len(casos)}")
    print("\nquem concorda com o rótulo:", dict(Counter(
        ("SR" if c["sr_acerta"] else "") + ("+núcleo" if c["nucleo_acerta"] else "") or "nenhum"
        for c in casos)))
    print("\nmecanismos (todos os casos):")
    for m, n in Counter(c["mecanismo"] for c in casos).most_common(25):
        print(f"   {n:4d}  {m}")
    grupos = defaultdict(list)
    for c in casos:
        grupos[c["mecanismo"]].append(c)
    if args.amostra:
        rng = random.Random(20261017)
        print(f"\namostra ({args.amostra} por mecanismo com 10+ casos):")
        for m, cs in sorted(grupos.items(), key=lambda x: -len(x[1])):
            if len(cs) < 10:
                continue
            print(f"\n## {m} ({len(cs)})")
            for c in rng.sample(cs, min(args.amostra, len(cs))):
                print(f"   {c['id']} | rótulo {c['rotulo']} | SR {c['sr']} | núcleo {c['nucleo']} {c['alcancaveis']}")
                print(f"      horizontes: {' '.join(c['horizontes'][:9])}")
                for f in c["rupturas"][:3]:
                    print(f"      · {f[:160]}")
    if args.json:
        args.json.write_text(json.dumps(casos, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
