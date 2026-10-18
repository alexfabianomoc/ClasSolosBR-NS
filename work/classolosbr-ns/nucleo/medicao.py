"""Próxima medição do Avaliador Parcial (monografia, §4.2.4).

    python -m nucleo.medicao PERFIL.json          # recomendação para cada perfil
    python -m nucleo.medicao --gerar-doadores     # refaz o arquivo de doadores

Quando o resultado não é conclusivo, a pergunta prática é qual determinação
analítica ou de campo fazer primeiro. A resposta é calculada pela própria
base de regras, sem estatística de rótulo:

1. **Unidade de medida.** Mede-se uma determinação inteira num horizonte —
   granulometria, complexo sortivo, carbono orgânico, pH, cor úmida, cor
   seca, estrutura —, e não um atributo isolado, porque é assim
   que a falta ocorre e que a medida é feita (é o recorte da ablação de
   `avaliacao_parcial`). Candidata é a unidade que falta num horizonte.
2. **Simulação com doadores.** Para cada candidata, a unidade é preenchida
   com os valores de `K` horizontes reais do Banco de Dados de Solos do
   Brasil com a mesma letra de horizonte principal e a unidade completa,
   escolhidos nos quantis do atributo principal da unidade, e o perfil é
   reclassificado. Cada doador é um desfecho possível da medição.
3. **Ganho de informação.** Com as classes alcançáveis tomadas como
   equiprováveis, a indefinição atual vale log2 |A|; a esperada depois da
   medição, a média de log2 |A'| sobre os doadores. O ganho é a diferença, em
   bits. Empata-se pela probabilidade de concluir (|A'| = 1).

⚠️ Hipóteses declaradas: (a) os doadores representam a distribuição marginal
da unidade no acervo, condicionada só à letra do horizonte — a correlação com
o resto do perfil é ignorada; (b) as classes alcançáveis são equiprováveis.
O critério não imputa nada: os valores dos doadores servem para prever o que
a medição pode decidir, e nunca entram no resultado do perfil.

🚨 Verificação embutida: pela monotonicidade (§4.2.4), todo desfecho tem de
estar contido no conjunto alcançável atual. Um desfecho fora dele é violação
de contenção e é devolvido em `violacoes`.

Pendências sem campo no contrato de entrada (as regras `Pendente`) não se
resolvem por medição e são listadas à parte.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .avaliador import Resultado, classificar
from .horizontes import principal
from .perfil import Horizonte, Perfil, _derivados, carregar_json

#: Determinações que se fazem de uma vez. O primeiro atributo ordena os
#: doadores (quantis); `falta` diz quando a unidade precisa ser medida.
UNIDADES: dict[str, tuple[str, ...]] = {
    "granulometria": ("ARGILA", "SILTE", "AREIA_GROS", "AREIA_FINA"),
    "complexo sortivo": ("CA_TROC", "MG_TROC", "K_TROC", "NA_TROC", "H_TROC", "AL_TROC"),
    "carbono orgânico": ("C_ORG",),
    "pH": ("PH_KCL", "PH_AGUA"),
    "cor úmida": ("COR_UMIDA_VALOR", "COR_UMIDA_CROMA", "COR_UMIDA_MATIZ"),
    "cor seca": ("COR_SECA_VALOR", "COR_SECA_CROMA", "COR_SECA_MATIZ"),
    "estrutura": ("ESTRUTURA_GRAU", "ESTRUTURA_TIPO", "ESTRUTURA_TAMANHO"),
}
# Cerosidade e mosqueado não entram: não registrados, são ausência observada
# ("quando constatada, deve ser descrita no campo", SiBCS 5ª ed., p. 44), e
# preenchê-los seria trocar uma observação, não medir o que falta (22º defeito,
# 2026-10-18).

#: Campos que acompanham a unidade no acervo e saem junto quando ela é
#: substituída (o laudo de Ca + Mg somados e o V informado no boletim).
ACOMPANHAM = {"complexo sortivo": ("_CA_MG_TROC", "_V_BOLETIM")}

#: Derivados que dependem das unidades e têm de ser recalculados.
DERIVADOS = ("SOMA_BASES", "CTC", "V_PERCENT", "ATIVIDADE_ARGILA")

DOADORES = Path(__file__).parent / "dados" / "doadores_medicao.json"
K_PADRAO = 15


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def falta(h: Horizonte, unidade: str) -> bool:
    """A unidade precisa ser medida neste horizonte?"""
    a = h.atributos
    if unidade == "complexo sortivo":
        return a.get("CTC") is None or a.get("V_PERCENT") is None
    if unidade == "granulometria":
        return any(a.get(x) is None for x in ("ARGILA", "AREIA_GROS", "AREIA_FINA"))
    if unidade == "estrutura":
        return a.get("ESTRUTURA_GRAU") is None
    return any(a.get(x) is None for x in UNIDADES[unidade])


def _completa(h: Horizonte, unidade: str) -> bool:
    if unidade == "complexo sortivo":
        return not falta(h, unidade) and _num(h.get("CA_TROC")) or (
            not falta(h, unidade) and _num(h.get("_CA_MG_TROC")))
    return not falta(h, unidade)


def preencher(perfil: Perfil, indice: int, unidade: str, valores: dict) -> Perfil:
    """Cópia do perfil com a unidade do horizonte trocada pelos `valores`."""
    q = copy.deepcopy(perfil)
    h = q.horizontes[indice]
    for nome in UNIDADES[unidade] + ACOMPANHAM.get(unidade, ()) + DERIVADOS:
        h.atributos.pop(nome, None)
    h.atributos.update({k: v for k, v in valores.items() if v is not None})
    h.atributos.update(_derivados(h))
    return q


def alcancaveis(r: Resultado) -> frozenset[str]:
    return frozenset(r.alcancaveis) | ({r.classe} if r.classe else frozenset())


# ------------------------------------------------------------ doadores ------

def gerar_doadores(por_grupo: int = 400, semente: int = 20261018) -> dict:
    """Amostra de horizontes do acervo com cada unidade completa, por letra."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    import bdsolos_adapter as adaptador
    from .perfil import de_dicionario
    brutos, _ = adaptador.ler_perfis()
    brutos = list(brutos.values()) if isinstance(brutos, dict) else brutos
    grupos: dict[str, dict[str, list]] = {}
    for b in brutos:
        p = de_dicionario(b)
        lev = str(p.id_ponto).split("|")[1] if "|" in str(p.id_ponto) else ""
        for h in p.horizontes:
            letra = principal(h)
            if not letra:
                continue
            for u in UNIDADES:
                if not _completa(h, u):
                    continue
                campos = UNIDADES[u] + ACOMPANHAM.get(u, ())
                grupos.setdefault(letra, {}).setdefault(u, []).append(
                    {"lev": lev, **{c: h.get(c) for c in campos if h.get(c) is not None}})
    rng = random.Random(semente)
    saida = {}
    for letra, us in grupos.items():
        for u, lista in us.items():
            if len(lista) > por_grupo:
                lista = rng.sample(lista, por_grupo)
            saida.setdefault(letra, {})[u] = lista
    return saida


_cache_doadores: dict | None = None


def ordenador(d: dict, unidade: str) -> float | None:
    """Atributo que ordena os doadores de uma unidade (para os quantis).

    É o primeiro de `UNIDADES`, salvo no complexo sortivo, ordenado por
    Ca + Mg: 35% a 45% dos doadores do acervo trazem só o laudo somado
    (`_CA_MG_TROC`), e ordenar pelo cálcio os jogava, sem ordem, para o fim
    da lista (corrigido em 2026-10-18, a partir de revisão do texto).
    """
    if unidade == "complexo sortivo":
        ca, mg = d.get("CA_TROC"), d.get("MG_TROC")
        if _num(ca) and _num(mg):
            return float(ca) + float(mg)
        v = d.get("_CA_MG_TROC")
        return float(v) if _num(v) else None
    v = d.get(UNIDADES[unidade][0])
    return float(v) if _num(v) else None


def doadores(letra: str, unidade: str, k: int, excluir_lev: str | None = None) -> list[dict]:
    """`k` doadores nos quantis do atributo que ordena a unidade (`ordenador`)."""
    global _cache_doadores
    if _cache_doadores is None:
        _cache_doadores = json.loads(DOADORES.read_text(encoding="utf-8"))
    lista = [d for d in _cache_doadores.get(letra, {}).get(unidade, [])
             if d.get("lev") != excluir_lev]
    if not lista:
        return []
    lista = sorted(lista, key=lambda d: (ordenador(d, unidade) is None,
                                         ordenador(d, unidade) or 0.0))
    if len(lista) <= k:
        return [{c: v for c, v in d.items() if c != "lev"} for d in lista]
    passos = [int((i + 0.5) * len(lista) / k) for i in range(k)]
    return [{c: v for c, v in lista[i].items() if c != "lev"} for i in passos]


# ------------------------------------------------------------ recomendação --

@dataclass
class Candidata:
    horizonte: str
    indice: int
    unidade: str
    ganho: float            # bits
    p_concluir: float
    desfechos: dict[frozenset, int] = field(default_factory=dict)


@dataclass
class Recomendacao:
    alcancaveis: frozenset
    candidatas: list[Candidata]
    sem_campo: list[str]
    pendencias: list[str] = field(default_factory=list)
    conclusivo: bool = False
    violacoes: list[tuple[str, str, frozenset]] = field(default_factory=list)


def _bits(n: int) -> float:
    return math.log2(n) if n > 0 else 0.0


def recomendar(perfil: Perfil, chave=None, k: int = K_PADRAO,
               excluir_lev: str | None = None,
               so: set[tuple[int, str]] | None = None) -> Recomendacao:
    """Ordena as medições possíveis pelo ganho de informação esperado.

    `so` restringe as candidatas a pares (índice do horizonte, unidade);
    serve à avaliação, que só pode "medir" o que ela própria removeu.
    """
    base = classificar(perfil, chave)
    A = alcancaveis(base)
    sem_campo = sorted({p for p in base.pendencias if p.startswith("pendente:")})
    rec = Recomendacao(A, [], sem_campo, list(dict.fromkeys(base.pendencias)),
                       base.conclusivo)
    if base.conclusivo:
        return rec
    antes = _bits(len(A))
    for i, h in enumerate(perfil.horizontes):
        letra = principal(h)
        for u in UNIDADES:
            if so is not None and (i, u) not in so:
                continue
            if so is None and not falta(h, u):
                continue
            ds = doadores(letra, u, k, excluir_lev)
            if not ds:
                continue
            desf: dict[frozenset, int] = {}
            for d in ds:
                r = classificar(preencher(perfil, i, u, d), chave)
                a2 = alcancaveis(r)
                desf[a2] = desf.get(a2, 0) + 1
                if not a2 <= A:
                    rec.violacoes.append((h.simbolo, u, a2))
            n = sum(desf.values())
            depois = sum(c * _bits(len(a)) for a, c in desf.items()) / n
            conclui = sum(c for a, c in desf.items() if len(a) == 1) / n
            rec.candidatas.append(Candidata(h.simbolo, i, u, antes - depois, conclui, desf))
    rec.candidatas.sort(key=lambda c: (-round(c.ganho, 9), -c.p_concluir, c.indice))
    return rec


def texto(rec: Recomendacao, n: int = 5) -> str:
    linhas = [f"alcançáveis: {', '.join(sorted(rec.alcancaveis)) or '—'}"]
    if rec.conclusivo:
        linhas.append("resultado conclusivo: nenhuma medição a recomendar")
        return "\n".join(linhas)
    uteis = [c for c in rec.candidatas if c.ganho > 0]
    if not uteis:
        linhas.append("nenhuma medição de unidade do contrato reduz o conjunto alcançável;"
                      " o que falta:")
        linhas += [f"  · {p}" for p in rec.pendencias if not p.startswith("pendente:")]
    for c in uteis[:n]:
        linhas.append(f"  {c.unidade:<17} em {c.horizonte:<8} ganho {c.ganho:.2f} bit"
                      f"  conclui em {100 * c.p_concluir:.0f}% dos desfechos simulados")
    if rec.sem_campo:
        linhas.append("sem campo no contrato (não se resolve por medição):")
        linhas += [f"  · {p}" for p in rec.sem_campo]
    if rec.violacoes:
        linhas.append(f"🚨 {len(rec.violacoes)} desfecho(s) fora do conjunto alcançável")
    return "\n".join(linhas)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo", nargs="?")
    ap.add_argument("--gerar-doadores", action="store_true")
    ap.add_argument("-k", type=int, default=K_PADRAO)
    args = ap.parse_args(argv)
    if args.gerar_doadores:
        d = gerar_doadores()
        DOADORES.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print({l: {u: len(v) for u, v in us.items()} for l, us in d.items()})
        return 0
    for perfil in carregar_json(args.arquivo):
        print(f"\n{perfil.id_ponto}")
        print(texto(recomendar(perfil, k=args.k)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
