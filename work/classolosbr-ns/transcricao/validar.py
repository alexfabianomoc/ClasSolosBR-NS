"""Validação do transcritor contra os JSON do conjunto curado.

    python -m transcricao.validar [--detalhe CAMPO]

O JSON de cada perfil é a transcrição feita pelos curadores da ficha
**final** — a atualizada, quando existe; a original, quando não houve
alteração. Transcrever essas mesmas fichas e comparar com o JSON mede o
transcritor antes de usá-lo nas fichas originais (CLAUDE.md, §13.3: um
critério é testado contra contraexemplo antes de ser usado como contagem).

As diferenças são separadas por tipo, porque nem toda diferença é erro do
transcritor:

* **valor × valor** — os dois têm número e discordam: erro do transcritor
  ou edição feita só no JSON (o registro de curadoria declara algumas);
* **só na ficha** — a ficha tem o valor, o JSON não: omissão na transcrição
  dos curadores (ex.: mosqueados) ou edição;
* **só no JSON** — o JSON tem, a ficha não: convenção (0 para granulometria
  não determinada) ou dado acrescentado pela curadoria (`PE_028`).

O arredondamento que os curadores aplicaram ao gravar o JSON (0,12 → 0,1)
não conta como diferença.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict

from nucleo.avaliacao import PYKKA7

from .ficha import transcrever
from .rtf_texto import ler

CAMPOS = ("SIMB_HORIZ", "LIMITE_SUP", "AREIA_GROS", "AREIA_FINA", "SILTE",
          "ARGILA", "PH_AGUA", "PH_KCL", "CA_TROC", "MG_TROC", "K_TROC",
          "NA_TROC", "AL_TROC", "H_TROC", "P_ASSIM", "C_ORG", "TEOR_FE",
          "TEOR_P", "EQUI_CACO3", "COND_ELETR", "COR_UMIDA_MATIZ",
          "COR_UMIDA_VALOR", "COR_UMIDA_CROMA", "COR_SECA_VALOR",
          "COR_SECA_CROMA")


def json_do_perfil(uf: str, ident: str) -> dict:
    caminho = PYKKA7 / uf / "json" / f"{ident}.json"
    dados, _ = json.JSONDecoder().raw_decode(caminho.read_text(encoding="utf-8"))
    return dados["items"][0]


def ficha(uf: str, ident: str, tipo: str):
    return PYKKA7 / uf / tipo / f"{ident}.rtf"


def ficha_final(uf: str, ident: str):
    atualizada = ficha(uf, ident, "updated")
    return atualizada if atualizada.exists() else ficha(uf, ident, "original")


def perfis():
    for uf in ("PE", "RN"):
        for caminho in sorted((PYKKA7 / uf / "json").glob("*.json")):
            if not caminho.name.endswith("_all.json"):
                yield uf, caminho.stem


def _casas(x) -> int:
    t = repr(float(x))
    if "e" in t:
        return 6
    t = t.rstrip("0").rstrip(".")
    return len(t.split(".")[1]) if "." in t else 0


def iguais(a, b) -> bool:
    """Ficha (a) e JSON (b) dizem o mesmo valor, a menos de arredondamento?"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    numericos = all(isinstance(x, (int, float)) and not isinstance(x, bool)
                    for x in (a, b))
    if numericos:
        a, b = float(a), float(b)
        tol = 1e-9 * max(1.0, abs(b))
        return abs(a - b) <= tol or abs(round(a, _casas(b)) - b) <= tol
    return str(a).strip() == str(b).strip()


def tipo_diferenca(a, b) -> str | None:
    if iguais(a, b):
        return None
    if a is None:
        return "só no JSON"
    if b is None:
        return "só na ficha"
    return "valor × valor"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", default=None)
    args = ap.parse_args(argv)

    por_campo = defaultdict(Counter)
    exemplos = defaultdict(list)
    contagem = Counter()
    desalinhados = []
    for uf, ident in perfis():
        ref = json_do_perfil(uf, ident)
        trans = transcrever(ler(ficha_final(uf, ident)))
        rh, th = ref.get("HORIZONTES") or [], trans["HORIZONTES"]
        if len(rh) != len(th):
            contagem["número de horizontes difere"] += 1
            desalinhados.append((ident, len(rh), len(th)))
            continue
        contagem["igual"] += 1
        for hr, ht in zip(rh, th):
            for c in CAMPOS:
                a, b = ht.get(c), hr.get(c)
                if a is None and b is None:
                    continue
                t = tipo_diferenca(a, b) or "igual"
                por_campo[c][t] += 1
                if t == "valor × valor":
                    exemplos[c].append((ident, hr.get("SIMB_HORIZ"), b, a))

    print("Validação do transcritor: ficha final × JSON do conjunto curado")
    print(f"perfis: {dict(contagem)}; desalinhados: {desalinhados}")
    print(f"{'campo':<17} {'igual':>6} {'valor×valor':>12} {'só ficha':>9} {'só JSON':>8}")
    for c in CAMPOS:
        k = por_campo[c]
        if not sum(k.values()):
            continue
        print(f"{c:<17} {k['igual']:>6} {k['valor × valor']:>12} "
              f"{k['só na ficha']:>9} {k['só no JSON']:>8}   {exemplos[c][:2]}")
    if args.detalhe:
        print(f"\nvalor × valor em {args.detalhe} (perfil, horizonte, JSON, ficha):")
        for e in exemplos[args.detalhe]:
            print("  ", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
