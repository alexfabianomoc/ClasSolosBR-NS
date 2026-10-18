"""Política do Inferidor na integração: quando acionar, que candidatos propor,
com que confiança, e quando se abster.

O componente devolve **símbolos**, nunca classe. Nenhuma função aqui conhece a
chave taxonômica: quem decide a classe — sempre condicional — é o núcleo, na
reexecução de cada cenário (`fluxo`).

Confiança. As saídas da rede e das árvores são probabilidades **marginais**:
uma distribuição sobre o horizonte principal e uma probabilidade por sufixo.
Nada no treino as calibra conjuntamente, e os sufixos não são independentes
(`t` e `w` quase se excluem). Por isso:

* o **escore** de um candidato — P(principal) × Π [p_s ou 1 − p_s] — é usado
  apenas para **ordenar** candidatos e cenários, e é reportado como "escore de
  ordenação (não calibrado)";
* a decisão de propor ou abster usa κ, a menor confiança entre as decisões
  sobre os sufixos de tipo, contra θ escolhido na validação
  (`integracao.modelos.escolhe_theta`);
* as confianças componentes acompanham cada candidato até a árvore de prova.
"""
from __future__ import annotations

import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "dags"))

from inferidor import dados as D  # noqa: E402
from nucleo.avaliador import simbolo_ausente  # noqa: E402
from nucleo.horizontes import (_leituras_discordam, b_sem_sufixo_legivel,  # noqa: E402
                               leitura_atual)
from sentinela import gramatica_sufixos as gs  # noqa: E402

from .modelos import SUFIXOS_TIPO, kappa  # noqa: E402

MAX_CANDIDATOS = 3
MAX_ALTERNATIVAS = 2

GATILHO_AUSENTE = "símbolo ausente"
GATILHO_SEM_TIPO = "B sem sufixo que designe o tipo"
GATILHO_DISCORDANTE = "símbolo antigo com leituras discordantes"

#: Sufixos de tipo de B (os que o `B` sem sufixo deixa pendentes) e os que ele nega.
SUFIXOS_TIPO_B = ("t", "w", "i", "h", "s")
SUFIXOS_NEGADOS_PELO_B = ("g", "f", "c", "v", "m")


def gatilho(simbolo: str) -> str | None:
    """Por que o Inferidor deve ser acionado neste horizonte, ou None."""
    if simbolo_ausente(simbolo):
        return GATILHO_AUSENTE
    if _leituras_discordam(simbolo):
        return GATILHO_DISCORDANTE
    moderno = leitura_atual(simbolo)
    if b_sem_sufixo_legivel(gs.analisa(moderno or simbolo)):
        return GATILHO_SEM_TIPO
    return None


def prefixo_e_principal(simbolo: str) -> tuple[str, str]:
    """('2', 'B') para '2B', '2Bt2', 'IIB2' (via notação atual)."""
    moderno = leitura_atual(simbolo) or simbolo
    a = gs.analisa(moderno)
    return (str(a.litologico) if a.litologico else ""), a.principal or ""


def assinatura(simbolo: str) -> tuple[str, frozenset]:
    """O que o núcleo lê do símbolo: letra(s) principal(is) e sufixos de tipo."""
    moderno = leitura_atual(simbolo) or simbolo
    a = gs.analisa(moderno)
    suf = frozenset(s.rstrip(gs.MACRON) for s in a.sufixos) & frozenset(SUFIXOS_TIPO + ("m",))
    return a.principal or "", suf


def bem_formado(simbolo: str) -> tuple[bool, list[str]]:
    a = gs.analisa(simbolo)
    if not a.reconhecido or not a.principal or a.mesclado:
        return False, ["não reconhecido pela gramática"]
    achados = [f"{x.codigo}: {x.gravidade}" for x in gs.valida(simbolo)
               if x.gravidade in ("erro", "alerta")]
    return not achados, achados


def _ordena_sufixos(sufixos) -> str:
    ordem = "".join(D.SUFIXOS_LIDOS)
    return "".join(sorted(sufixos, key=lambda s: ordem.index(s) if s in ordem else 99))


@dataclass
class Candidato:
    simbolo: str
    forma: str                     # "complementação" | "proposta completa" | "leitura da norma"
    escore: float                  # de ORDENAÇÃO, não calibrado
    kappa: float                   # confiança das decisões de tipo
    p_principal: float
    p_sufixos: dict = field(default_factory=dict)
    bem_formado: bool = True
    achados_gramatica: list = field(default_factory=list)

    def assinatura(self):
        return assinatura(self.simbolo)


@dataclass
class Proposta:
    horizonte_id: str
    simbolo_anotado: str
    gatilho: str
    modelo: str
    candidatos: list[Candidato] = field(default_factory=list)
    abstencao: str | None = None

    def como_dict(self) -> dict:
        d = asdict(self)
        d["escore_e_calibrado"] = False
        return d


class Inferidor:
    """Adaptador entre um `Estimador` e o fluxo. `estimador=None` ⇒ indisponível."""

    def __init__(self, estimador=None, motivo_indisponivel: str = "modelo não carregado"):
        self.estimador = estimador
        self.motivo_indisponivel = motivo_indisponivel

    @property
    def disponivel(self) -> bool:
        return self.estimador is not None

    @property
    def id(self) -> str:
        return self.estimador.id if self.estimador else "indisponível"

    # -------------------------------------------------------------- base --
    def _probabilidades(self, bruto: dict, ks: list[int]):
        hs = bruto.get("HORIZONTES") or []
        ordem = D.em_ordem(bruto)
        linhas = []
        for k in ks:
            i = next(j for j, x in enumerate(ordem) if x is hs[k])
            linhas.append(D.atributos(bruto, i, ordem))
        pp, ps = self.estimador.proba(linhas)
        return pp, ps

    def _escore(self, pp_linha, ps_linha, principal: str, sufixos: set[str]) -> tuple[float, float]:
        classes = self.estimador.classes
        chave = principal if principal in classes else ("outro" if "outro" in classes else None)
        p_pr = float(pp_linha[classes.index(chave)]) if chave is not None else 0.0
        e = p_pr
        for j, s in enumerate(D.SUFIXOS_LIDOS):
            e *= float(ps_linha[j]) if s in sufixos else 1.0 - float(ps_linha[j])
        return e, p_pr

    def _candidato(self, pp_l, ps_l, prefixo, principal, sufixos, forma) -> Candidato:
        simbolo = f"{prefixo}{principal}{_ordena_sufixos(sufixos)}"
        esc, p_pr = self._escore(pp_l, ps_l, principal, set(sufixos))
        ok, achados = bem_formado(simbolo)
        aplic = SUFIXOS_TIPO if principal.startswith("B") else tuple(s for s in SUFIXOS_TIPO if s in "gfcvh")
        return Candidato(simbolo, forma, esc, kappa(ps_l, set(sufixos), aplic), p_pr,
                         {s: round(float(ps_l[j]), 4) for j, s in enumerate(D.SUFIXOS_LIDOS)},
                         ok, achados)

    # ----------------------------------------------------------- propostas --
    def propor(self, bruto: dict, gatilhos: dict[int, str]) -> list[Proposta]:
        hs = bruto.get("HORIZONTES") or []
        if not gatilhos:
            return []
        if not self.disponivel:
            return [Proposta(str(k), hs[k].get("SIMB_HORIZ") or "", g, "indisponível",
                             abstencao=f"modelo indisponível ({self.motivo_indisponivel})")
                    for k, g in gatilhos.items()]
        ks = list(gatilhos)
        try:
            pp, ps = self._probabilidades(bruto, ks)
        except Exception as exc:  # o fluxo segue com a resposta observacional
            return [Proposta(str(k), hs[k].get("SIMB_HORIZ") or "", g, self.id,
                             abstencao=f"falha do modelo: {type(exc).__name__}: {exc}")
                    for k, g in gatilhos.items()]
        lim = self.estimador.limiares
        saida = []
        for n, k in enumerate(ks):
            anotado = hs[k].get("SIMB_HORIZ") or ""
            g = gatilhos[k]
            prop = Proposta(str(k), anotado, g, self.id)
            pp_l, ps_l = pp[n], ps[n]
            decididos = {s for j, s in enumerate(D.SUFIXOS_LIDOS) if ps_l[j] >= lim[j]}
            if g == GATILHO_DISCORDANTE:
                cands = []
                for leitura in gs.leituras(anotado):
                    pref, pr = prefixo_e_principal(leitura)
                    a = gs.analisa(leitura)
                    suf = {s.rstrip(gs.MACRON) for s in a.sufixos}
                    c = self._candidato(pp_l, ps_l, "", pr, suf, "leitura da norma")
                    c.simbolo = leitura
                    cands.append(c)
            else:
                if g == GATILHO_AUSENTE:
                    classes = self.estimador.classes
                    principal = str(classes[int(pp_l.argmax())])
                    pref = ""
                    if principal == "outro":
                        prop.abstencao = "principal proposto fora das classes treinadas ('outro')"
                        saida.append(prop)
                        continue
                    forma = "proposta completa"
                else:
                    pref, principal = prefixo_e_principal(anotado)
                    forma = "complementação"
                aplic = SUFIXOS_TIPO if principal.startswith("B") else tuple(
                    s for s in SUFIXOS_TIPO if s in "gfcvh")
                base = set(decididos)
                if g == GATILHO_SEM_TIPO:
                    # Complementação só com sufixos de tipo de B (rodada v1): o `B`
                    # sem sufixo deixa pendentes apenas os tipos de B (decisão de
                    # 2026-10-15) e nega g, f, c, v; acrescentá-los contradiria a
                    # anotação — isso é hipótese de anotação, não complemento.
                    base -= set(SUFIXOS_NEGADOS_PELO_B)
                    aplic = SUFIXOS_TIPO_B
                cands = [self._candidato(pp_l, ps_l, pref, principal, base, forma)]
                # alternativas: inverte os sufixos de tipo mais próximos do limiar
                margem = sorted(((abs(math.log((ps_l[j] + 1e-9) / (1 - ps_l[j] + 1e-9))
                                      - math.log((lim[j] + 1e-9) / (1 - lim[j] + 1e-9))), s)
                                 for j, s in enumerate(D.SUFIXOS_LIDOS) if s in aplic))
                for _, s in margem[:MAX_ALTERNATIVAS]:
                    cands.append(self._candidato(pp_l, ps_l, pref, principal, base ^ {s}, forma))
            vistos, unicos = set(), []
            for c in sorted(cands, key=lambda c: -c.escore):
                if c.assinatura() in vistos:
                    continue
                vistos.add(c.assinatura())
                unicos.append(c)
            prop.candidatos = unicos[:MAX_CANDIDATOS]
            validos = [c for c in prop.candidatos if c.bem_formado]
            topo = validos[0] if validos else None
            if topo is None:
                prop.abstencao = "nenhum candidato bem-formado pela gramática do Sentinela"
            elif g != GATILHO_DISCORDANTE and not (topo.assinatura()[1] & set(SUFIXOS_TIPO)) \
                    and topo.assinatura()[0].startswith("B"):
                prop.abstencao = "o candidato principal não informa o tipo do horizonte"
            elif g != GATILHO_DISCORDANTE and topo.kappa < self.estimador.theta:
                prop.abstencao = (f"confiança de tipo κ = {topo.kappa:.3f} abaixo de "
                                  f"θ = {self.estimador.theta:g}")
            elif g == GATILHO_DISCORDANTE and topo.kappa < self.estimador.theta:
                prop.abstencao = (f"confiança de tipo κ = {topo.kappa:.3f} abaixo de "
                                  f"θ = {self.estimador.theta:g}")
            saida.append(prop)
        return saida

    # -------------------------------------------------------- conflitos --
    def conflitos(self, bruto: dict, ks: list[int]) -> list[dict]:
        """Conflito anotado × proposto nos horizontes de símbolo informativo.

        Sinal = 1 − escore(símbolo anotado). Há conflito quando o sinal passa
        de τ e a assinatura proposta difere da anotada. O resultado é
        **hipótese de anotação**: nunca altera o símbolo nem a classe.
        """
        if not self.disponivel or not ks:
            return []
        hs = bruto.get("HORIZONTES") or []
        try:
            pp, ps = self._probabilidades(bruto, ks)
        except Exception:
            return []
        lim = self.estimador.limiares
        classes = self.estimador.classes
        saida = []
        for n, k in enumerate(ks):
            anotado = hs[k].get("SIMB_HORIZ") or ""
            leituras = [leitura_atual(anotado) or anotado]
            melhor = 0.0
            for l in leituras:
                a = gs.analisa(l)
                suf = {s.rstrip(gs.MACRON) for s in a.sufixos} & set(D.SUFIXOS_LIDOS)
                melhor = max(melhor, self._escore(pp[n], ps[n], a.principal or "", suf)[0])
            sinal = 1.0 - melhor
            principal = str(classes[int(pp[n].argmax())])
            decididos = {s for j, s in enumerate(D.SUFIXOS_LIDOS) if ps[n][j] >= lim[j]}
            pref, pr_anot = prefixo_e_principal(anotado)
            propostos = []
            if principal != "outro":
                propostos.append(self._candidato(pp[n], ps[n], pref, principal, decididos,
                                                 "proposta completa"))
            # complementação: principal anotado, sufixos de tipo propostos
            if pr_anot:
                a = gs.analisa(leitura_atual(anotado) or anotado)
                nao_tipo = {s.rstrip(gs.MACRON) for s in a.sufixos} - set(SUFIXOS_TIPO)
                propostos.append(self._candidato(
                    pp[n], ps[n], pref, pr_anot,
                    nao_tipo | (decididos & set(SUFIXOS_TIPO)), "complementação"))
            ass_anot = assinatura(anotado)
            diferentes = [c for c in propostos if c.bem_formado and c.assinatura() != ass_anot]
            saida.append({"horizonte_id": str(k), "simbolo_anotado": anotado,
                          "sinal": round(sinal, 6), "tau": self.estimador.tau,
                          "conflito": bool(sinal >= self.estimador.tau and diferentes),
                          "candidatos": [asdict(c) for c in diferentes],
                          "modelo": self.id, "escore_e_calibrado": False})
        return saida
