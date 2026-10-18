"""Conjunto de horizontes do Inferidor (monografia, §4.2.5).

Cada linha é um horizonte, com:

* **atributos** do próprio horizonte, lidos do contrato de entrada (o mesmo
  formato do BDSolos convertido e das fichas transcritas do conjunto curado),
  mais derivados do complexo sortivo e indicadores de valor ausente;
* **contexto no perfil**: profundidade, espessura, posição na sequência e os
  atributos-chave dos horizontes imediatamente acima e abaixo;
* **rótulos**, lidos do símbolo anotado: o horizonte principal (`A`, `B`, `AB`,
  `BA`...) e os 17 sufixos que o sistema de referência lê (§2.5).

Entram no treino só símbolos **bem-formados** sob a norma de notação
(gramática do Sentinela, `dags/sentinela/gramatica_sufixos.py`): a notação
anterior é convertida quando a tradução é unívoca e excluída quando não é; e o
horizonte B cujo símbolo não informa o tipo fica fora, porque é justamente o
que o componente deve completar (decisão de 2026-10-16, opção ii).
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "dags"))
sys.path.insert(0, str(RAIZ.parents[1] / "tools"))

from sentinela import gramatica_sufixos as gs  # noqa: E402
from nucleo.horizontes import b_sem_sufixo_legivel  # noqa: E402
from nucleo.perfil import matiz_numerico  # noqa: E402

#: Os 17 sufixos que alteram a classe em pelo menos um nível no sistema de
#: referência (caracterização experimental, §2.5 da monografia).
SUFIXOS_LIDOS = ("c", "d", "f", "g", "h", "i", "j", "k", "m", "n", "o", "r",
                 "s", "t", "v", "w", "x")

NUMERICOS = (
    "COR_UMIDA_VALOR", "COR_UMIDA_CROMA", "COR_SECA_VALOR", "COR_SECA_CROMA",
    "COR_MOSQ_VALOR_1", "COR_MOSQ_CROMA_1",
    "ESTRUTURA_GRAU", "ESTRUTURA_TAMANHO", "CEROSIDADE_GRAU", "CEROSIDADE_QUANTIDADE",
    "CONSISTENCIA_SECO", "TRANSICAO_GRAU", "TRANSICAO_FORMA",
    "CALHAU", "CASCALHO", "AREIA_GROS", "AREIA_FINA", "SILTE", "ARGILA",
    "PH_AGUA", "PH_KCL", "C_ORG", "CA_TROC", "MG_TROC", "K_TROC", "NA_TROC",
    "AL_TROC", "H_TROC", "P_ASSIM", "COND_ELETR", "EQUI_CACO3", "TEOR_FE",
)
MATIZES = ("COR_UMIDA_MATIZ", "COR_SECA_MATIZ", "COR_MOSQ_MATIZ_1")
BOOLEANOS = ("RETRATIL", "COESO", "FLUVICO", "SOMBRICO", "REDOXICO",
             "MATERIAIS_PRIMARIOS", "ATIVIDADES_HUMANAS", "PLACICO_TOPO")
TIPOS_ESTRUTURA = range(1, 8)
#: Atributos dos vizinhos (acima e abaixo) que entram como contexto.
CONTEXTO = ("ARGILA", "C_ORG", "COR_UMIDA_VALOR", "COR_UMIDA_CROMA",
            "_MATIZ_UMIDA", "_V", "ESTRUTURA_GRAU")
ABERTO = 1000.0   # limites a partir daqui são "horizonte aberto" (10000 no contrato)


def _num(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _derivados(h: dict) -> dict:
    ca, mg = _num(h.get("CA_TROC")), _num(h.get("MG_TROC"))
    camg = ca + mg if None not in (ca, mg) else _num(h.get("_CA_MG_TROC"))
    k, na, hh, al = (_num(h.get(c)) for c in ("K_TROC", "NA_TROC", "H_TROC", "AL_TROC"))
    d = {"_S": None, "_T": None, "_V": None, "_ATIV": None,
         "_MATIZ_UMIDA": matiz_numerico(h.get("COR_UMIDA_MATIZ"))}
    if None not in (camg, k, na):
        s = camg + k + na
        d["_S"] = s
        if None not in (hh, al):
            t = s + hh + al
            d["_T"] = t
            d["_V"] = 100 * s / t if t > 0 else None
            arg = _num(h.get("ARGILA"))
            d["_ATIV"] = 1000 * t / arg if arg else None
    if d["_V"] is None:
        d["_V"] = _num(h.get("_V_BOLETIM"))
    return d


def nomes_atributos() -> list[str]:
    nomes = ["prof_topo", "prof_base", "espessura", "aberto", "posicao", "posicao_rel",
             "n_horizontes", "drenagem"]
    nomes += list(NUMERICOS) + ["_S", "_T", "_V", "_ATIV"]
    nomes += [f"{m}_num" for m in MATIZES] + [f"{m}_N" for m in MATIZES]
    nomes += [f"estrutura_tipo_{t}" for t in TIPOS_ESTRUTURA]
    nomes += list(BOOLEANOS)
    nomes += [f"acima_{c}" for c in CONTEXTO] + [f"abaixo_{c}" for c in CONTEXTO]
    nomes += ["delta_argila_acima", "delta_argila_abaixo"]
    return nomes


def atributos(perfil: dict, i: int, ordem: list[dict]) -> list[float | None]:
    """Vetor de atributos do horizonte `ordem[i]` (horizontes já em ordem de profundidade)."""
    h = ordem[i]
    der = _derivados(h)
    topo, base = _num(h.get("LIMITE_SUP")), _num(h.get("LIMITE_INF"))
    aberto = base is not None and base >= ABERTO
    esp = base - topo if None not in (topo, base) and not aberto else None
    n = len(ordem)
    v = [topo, None if aberto else base, esp, 1.0 if aberto else 0.0, float(i),
         i / (n - 1) if n > 1 else 0.0, float(n), _num(perfil.get("DRENAGEM"))]
    v += [_num(h.get(c)) for c in NUMERICOS]
    v += [der["_S"], der["_T"], der["_V"], der["_ATIV"]]
    v += [matiz_numerico(h.get(m)) for m in MATIZES]
    v += [1.0 if str(h.get(m) or "").strip().upper().startswith("N") else
          (0.0 if h.get(m) else None) for m in MATIZES]
    tipo = _num(h.get("ESTRUTURA_TIPO"))
    v += [None if tipo is None else (1.0 if tipo == t else 0.0) for t in TIPOS_ESTRUTURA]
    v += [None if h.get(b) is None else (1.0 if h.get(b) else 0.0) for b in BOOLEANOS]
    viz = []
    for j in (i - 1, i + 1):
        if 0 <= j < n:
            hv = ordem[j]
            dv = _derivados(hv)
            viz.append([dv[c] if c.startswith("_") else _num(hv.get(c)) for c in CONTEXTO])
        else:
            viz.append([None] * len(CONTEXTO))
    v += viz[0] + viz[1]
    arg = _num(h.get("ARGILA"))
    v += [None if None in (arg, viz[0][0]) else arg - viz[0][0],
          None if None in (arg, viz[1][0]) else viz[1][0] - arg]
    return v


def simbolo_de_treino(bruto: str) -> str | None:
    """O símbolo, na notação vigente, se pode servir de rótulo; senão None."""
    if not bruto or not bruto.strip():
        return None
    moderno = gs.moderniza(bruto)
    s = moderno or bruto
    a = gs.analisa(s)
    if not a.reconhecido or a.mesclado or not a.principal:
        return None
    if any(x.gravidade in ("erro", "alerta") for x in gs.valida(s)):
        return None
    if b_sem_sufixo_legivel(a):
        return None
    return s


def rotulos(simbolo: str) -> tuple[str, tuple[int, ...]]:
    a = gs.analisa(simbolo)
    return a.principal, tuple(1 if s in a.sufixos else 0 for s in SUFIXOS_LIDOS)


def em_ordem(perfil: dict) -> list[dict]:
    hs = list(perfil.get("HORIZONTES") or [])
    return sorted(hs, key=lambda h: (_num(h.get("LIMITE_SUP")) if _num(h.get("LIMITE_SUP")) is not None else 1e9))


@dataclass
class Conjunto:
    X: list[list[float | None]] = field(default_factory=list)
    principal: list[str] = field(default_factory=list)
    sufixos: list[tuple[int, ...]] = field(default_factory=list)
    grupo: list[str] = field(default_factory=list)       # levantamento
    ordem_solo: list[str] = field(default_factory=list)  # ordem registrada do perfil
    simbolo: list[str] = field(default_factory=list)
    perfil: list[str] = field(default_factory=list)
    descartados: dict = field(default_factory=dict)


def do_bdsolos() -> Conjunto:
    """Horizontes rotulados do BDSolos, sem os registros que repetem o conjunto curado."""
    import bdsolos_adapter as B
    perfis, _ = B.ler_perfis()
    perfis = B.filtrar(perfis, sem_curado=True)
    c = Conjunto(descartados={"sem símbolo utilizável": 0, "B sem tipo": 0})
    for p in perfis:
        ordem = em_ordem(p)
        for i, h in enumerate(ordem):
            bruto = h.get("SIMB_HORIZ") or ""
            s = simbolo_de_treino(bruto)
            if s is None:
                a = gs.analisa(gs.moderniza(bruto) or bruto)
                chave = "B sem tipo" if a.reconhecido and b_sem_sufixo_legivel(a) else "sem símbolo utilizável"
                c.descartados[chave] += 1
                continue
            pr, sf = rotulos(s)
            c.X.append(atributos(p, i, ordem))
            c.principal.append(pr)
            c.sufixos.append(sf)
            c.grupo.append(str(p.get("ID_PONTO", "")).split("|")[1])
            c.ordem_solo.append((p.get("ORDEM") or "").upper())
            c.simbolo.append(s)
            c.perfil.append(p.get("ID_PONTO"))
    return c
