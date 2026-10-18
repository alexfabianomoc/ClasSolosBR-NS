"""Monta, para cada perfil curado, a versão **original** no formato do contrato.

    python -m transcricao.originais

Insumo do Acerto@k sobre casos reais (monografia, §3.4). Para cada perfil
há três leituras: o JSON curado (J), a ficha final (U — a atualizada, quando
existe; senão a original) e a ficha original (O). U e O passam pelo mesmo
transcritor (`ficha.py`). A regra, campo a campo, é:

1. O difere de U → vale **O**: a ficha mudou na curadoria;
2. O igual a U, e U igual a J (a menos do arredondamento do JSON) → vale
   **J**: nada mudou, e mantém-se a convenção dos curadores;
3. O igual a U, e U difere de J → vale **O**: a curadoria corrigiu só o JSON
   (ex.: `PE_007`, MG_TROC 17 → 1,7; `PE_009`, silte recalculado).

A regra cancela os erros sistemáticos do transcritor, que afetam O e U do
mesmo modo, e preserva tudo o que a ficha original diz. O que não sai da
ficha (estrutura, cerosidade, booleanos) vem de J, e a lista de campos
alterados registra **só** o que sai da ficha.

⚠️ O transcritor foi validado contra o JSON antes deste uso
(`python -m transcricao.validar`, 2026-10-15): 92 dos 94 perfis alinham
horizonte a horizonte.

Saída: `transcricao/originais/<ID>.json`, com `_ALTERACOES` — a lista do que
a curadoria mudou, horizonte a horizonte, com a **natureza** da mudança —
valor corrigido (os dois lados têm valor e discordam), acrescentado na
curadoria (a ficha não tinha: convenções como 0 para granulometria não
determinada, Ca e Mg separados de uma soma, cor seca incluída) ou omitido na
curadoria (a ficha tinha, o JSON não) — e `_AVISOS` do transcritor.
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path

from .ficha import transcrever
from .rtf_texto import ler
from .validar import ficha, ficha_final, iguais, json_do_perfil, perfis

#: Campos lidos da ficha e comparados. Mosqueados ficam de fora: os curadores
#: quase nunca os transcreveram, e a diferença seria omissão, não correção.
CAMPOS = ("SIMB_HORIZ", "LIMITE_SUP", "AREIA_GROS", "AREIA_FINA", "SILTE",
          "ARGILA", "PH_AGUA", "PH_KCL", "CA_TROC", "MG_TROC", "K_TROC",
          "NA_TROC", "AL_TROC", "H_TROC", "P_ASSIM", "C_ORG", "TEOR_FE",
          "TEOR_P", "EQUI_CACO3", "COND_ELETR", "COR_UMIDA_MATIZ",
          "COR_UMIDA_VALOR", "COR_UMIDA_CROMA", "COR_SECA_MATIZ",
          "COR_SECA_VALOR", "COR_SECA_CROMA")

SAIDA = Path(__file__).parent / "originais"


def _alinhar(a: list[dict], b: list[dict]) -> list[tuple[int, int]]:
    """Pares de índices (a, b): pela posição, ou pelo limite superior."""
    if len(a) == len(b):
        return list(zip(range(len(a)), range(len(b))))
    pares = []
    usados = set()
    for i, ha in enumerate(a):
        sa = ha.get("LIMITE_SUP")
        for j, hb in enumerate(b):
            sb = hb.get("LIMITE_SUP")
            if j in usados or sa is None or sb is None:
                continue
            if abs(abs(float(sa)) - abs(float(sb))) < 1e-6:
                pares.append((i, j))
                usados.add(j)
                break
    return pares


def montar(uf: str, ident: str) -> dict:
    j = json_do_perfil(uf, ident)
    u = transcrever(ler(ficha_final(uf, ident)))
    tem_atualizada = ficha(uf, ident, "updated").exists()
    o = transcrever(ler(ficha(uf, ident, "original"))) if tem_atualizada else u

    jh, uh, oh = j.get("HORIZONTES") or [], u["HORIZONTES"], o["HORIZONTES"]
    ju = dict((jj, ui) for jj, ui in _alinhar(jh, uh))   # J → U
    uo = dict((ui, oi) for ui, oi in _alinhar(uh, oh))   # U → O

    original = copy.deepcopy(j)
    alteracoes, avisos = [], list(u["_AVISOS"])
    if tem_atualizada:
        avisos += [f"original: {a}" for a in o["_AVISOS"]]
    nao_alinhados = []
    for jj, hj in enumerate(jh):
        ui = ju.get(jj)
        oi = uo.get(ui) if ui is not None else None
        if ui is None or oi is None:
            nao_alinhados.append(hj.get("SIMB_HORIZ"))
            continue
        hu, ho = uh[ui], oh[oi]
        destino = original["HORIZONTES"][jj]
        for c in CAMPOS:
            vo, vu, vj = ho.get(c), hu.get(c), hj.get(c)
            if not iguais(vo, vu):
                origem = "ficha alterada"
            elif iguais(vu, vj):
                continue
            else:
                origem = "só o JSON alterado"
            if vo is None:
                destino.pop(c, None)
            else:
                destino[c] = vo
            if vo is not None and vj is not None:
                natureza = "valor corrigido"
            elif vo is None:
                natureza = "acrescentado na curadoria"
            else:
                natureza = "omitido na curadoria"
            alteracoes.append({"horizonte": jj, "simbolo_json": hj.get("SIMB_HORIZ"),
                               "campo": c, "original": vo, "curado": vj,
                               "origem": origem, "natureza": natureza})
        if ho.get("_CA_MG_SOMADOS") is not None:
            destino["_CA_MG_SOMADOS"] = ho["_CA_MG_SOMADOS"]
    if nao_alinhados:
        avisos.append(f"horizontes do JSON sem par na ficha (mantidos como no "
                      f"JSON): {nao_alinhados}")
    original["_ALTERACOES"] = alteracoes
    original["_AVISOS"] = avisos
    original["_TEM_FICHA_ATUALIZADA"] = tem_atualizada
    original["_CLASSIFICACAO_FICHA_ORIGINAL"] = o.get("_CLASSIFICACAO_FICHA")
    original["_CLASSIFICACAO_FICHA_FINAL"] = u.get("_CLASSIFICACAO_FICHA")
    return original


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    SAIDA.mkdir(exist_ok=True)
    resumo = Counter()
    por_campo = Counter()
    for uf, ident in perfis():
        orig = montar(uf, ident)
        (SAIDA / f"{ident}.json").write_text(
            json.dumps({"items": [orig]}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        alt = orig["_ALTERACOES"]
        resumo["perfis"] += 1
        resumo["com alteração" if alt else "sem alteração"] += 1
        for a in alt:
            por_campo[(a["campo"], a["natureza"])] += 1
    print(f"Fichas originais montadas em {SAIDA}")
    print(dict(resumo))
    for (c, o), n in sorted(por_campo.items()):
        print(f"   {c:<17} {o:<20} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
