"""Avaliação do Avaliador Parcial por ablação controlada de atributos.

    python -m nucleo.avaliacao_parcial [--json SAIDA.json]

Protocolo (monografia, Quadro 7 e §3.4): parte-se dos perfis do conjunto
curado cuja classificação é **conclusiva** com todos os atributos; a classe
assim derivada é a "verdadeira" da ablação. Remove-se então um atributo —
em todos os horizontes do perfil, e com os derivados recalculados — e
reclassifica-se. Mede-se:

* **contenção** — a classe verdadeira continua no conjunto alcançável. Espera-
  se 100%: valor menor indica erro de implementação, não desempenho (§3.4);
* **tamanho do conjunto alcançável** depois da remoção;
* **conclusividade** — em quantas remoções o núcleo ainda conclui.

Duas ablações: atributo isolado e grupo de atributos (complexo sortivo,
granulometria, cor), este segundo para simular a falta de uma determinação
analítica inteira, que é como a ausência ocorre na prática.

⚠️ O que esta avaliação **não** mede: a substituição do resultado
desconhecido do sistema de referência por resposta parcial, que exige a
linha de base (Aviso 6 da monografia).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .avaliacao import PYKKA7
from .avaliador import classificar
from .estatistica import fmt, wilson
from .explicador import ATRIBUTOS_ANALITICOS, ATRIBUTOS_COR
from .perfil import _derivados, carregar_json

GRUPOS = {
    "complexo sortivo": ("CA_TROC", "MG_TROC", "K_TROC", "NA_TROC", "H_TROC", "AL_TROC"),
    "granulometria": ("ARGILA", "SILTE", "AREIA_GROS", "AREIA_FINA"),
    "cor úmida": ("COR_UMIDA_VALOR", "COR_UMIDA_CROMA"),
    "cor seca": ("COR_SECA_VALOR", "COR_SECA_CROMA"),
    "carbono orgânico": ("C_ORG",),
    "pH": ("PH_AGUA", "PH_KCL"),
}


def remover(perfil, atributos):
    """Cópia do perfil sem os atributos, em todos os horizontes."""
    q = copy.deepcopy(perfil)
    for h in q.horizontes:
        for a in atributos:
            h.atributos.pop(a, None)
        for d in ("SOMA_BASES", "CTC", "V_PERCENT", "ATIVIDADE_ARGILA"):
            h.atributos.pop(d, None)
        h.atributos.update(_derivados(h))
    return q


def _presente(perfil, atributos) -> bool:
    return any(isinstance(h.get(a), (int, float)) and not isinstance(h.get(a), bool)
               for h in perfil.horizontes for a in atributos)


def ablacao(perfis, unidades: dict[str, tuple[str, ...]]):
    linhas = []
    for p in perfis:
        limpo = classificar(p)
        if not limpo.conclusivo:
            continue
        for nome, atributos in unidades.items():
            if not _presente(p, atributos):
                continue
            r = classificar(remover(p, atributos))
            alc = set(r.alcancaveis) | ({r.classe} if r.classe else set())
            linhas.append({"perfil": p.id_ponto, "unidade": nome,
                           "verdadeira": limpo.classe,
                           "contem": limpo.classe in alc,
                           "tamanho": len(alc),
                           "conclusivo": r.conclusivo,
                           "alcancaveis": sorted(alc)})
    return linhas


def relatorio(titulo, linhas) -> dict:
    n = len(linhas)
    contem = sum(l["contem"] for l in linhas)
    concl = sum(l["conclusivo"] for l in linhas)
    nao_concl = [l for l in linhas if not l["conclusivo"]]
    tam = [l["tamanho"] for l in nao_concl]
    print(f"\n{titulo} — {n} remoções em {len({l['perfil'] for l in linhas})} perfis")
    print("-" * 72)
    print(f"contenção:              {contem}/{n}  {fmt(wilson(contem, n))}")
    print(f"ainda conclusivo:       {concl}/{n}  {fmt(wilson(concl, n))}")
    print(f"não conclusivo:         {len(nao_concl)}/{n}; tamanho médio do conjunto"
          f" alcançável nesses: {sum(tam) / max(1, len(tam)):.2f}"
          f" (distribuição {dict(sorted(Counter(tam).items()))})")
    por_unidade = defaultdict(lambda: [0, 0])
    for l in linhas:
        por_unidade[l["unidade"]][0] += 1
        por_unidade[l["unidade"]][1] += 0 if l["conclusivo"] else 1
    afetam = sorted(((u, v[1], v[0]) for u, v in por_unidade.items() if v[1]),
                    key=lambda x: -x[1])
    if afetam:
        print("remoções que tiram a conclusão, por unidade:")
        for u, k, tot in afetam:
            print(f"   {u:<22} {k}/{tot}")
    falhas = [l for l in linhas if not l["contem"]]
    for l in falhas:
        print(f"   🚨 contenção violada: {l['perfil']} sem {l['unidade']}:"
              f" {l['verdadeira']} fora de {l['alcancaveis']}")
    return {"remocoes": n, "contencao": contem, "conclusivo": concl,
            "tamanho_medio_nao_conclusivo": sum(tam) / max(1, len(tam)),
            "distribuicao_tamanho": dict(Counter(tam)),
            "afetam": {u: [k, tot] for u, k, tot in afetam},
            "violacoes": [(l["perfil"], l["unidade"]) for l in falhas]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    if not PYKKA7.exists():
        print(f"conjunto curado não encontrado em {PYKKA7}", file=sys.stderr)
        return 2
    arquivos = [a for a in sorted(PYKKA7.rglob("*.json"))
                if not a.name.endswith("_all.json")]
    perfis = [p for a in arquivos for p in carregar_json(a)]
    conclusivos = sum(1 for p in perfis if classificar(p).conclusivo)
    print("Avaliação do Avaliador Parcial por ablação controlada")
    print("=" * 72)
    print(f"perfis: {len(perfis)}; conclusivos com todos os atributos: {conclusivos}")

    isolados = {a: (a,) for a in ATRIBUTOS_ANALITICOS + ATRIBUTOS_COR}
    saida = {"perfis": len(perfis), "conclusivos": conclusivos,
             "atributo_isolado": relatorio("Atributo isolado", ablacao(perfis, isolados)),
             "grupo": relatorio("Grupo de atributos", ablacao(perfis, GRUPOS))}
    print("\nLeitura. A contenção é verificação de corretude: espera-se 100%,")
    print("e o intervalo de Wilson diz o limite inferior que o tamanho permite.")
    if args.json:
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
