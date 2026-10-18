"""O explicador de divergências — abdução contrastiva (monografia, §4.3).

Uma **divergência** é a classe registrada na ficha ficar **fora do conjunto
alcançável** do perfil (§4.3.1, compromisso (d) do checklist de 2026-10-15).
Se a classe registrada continua alcançável sem que o resultado seja
conclusivo, a diferença é incompletude, e cabe ao Avaliador Parcial.

A refutação tem duas origens, e as duas são registradas (compromisso (a)):

1. a condição da própria classe registrada é falsa;
2. a condição é verdadeira ou indeterminada, mas uma classe que a precede na
   chave foi concluída antes.

As hipóteses são de **alteração de um único atributo** (|Aj| = 1). Para cada
atributo numérico de cada horizonte, uma busca sobre o valor (compromisso (b))
procura o menor ajuste que faz o perfil alterado derivar a classe registrada:
sondas — os deslocamentos de separador decimal (×/÷ 10, 100, 1000), zero e
três valores acima do informado (v + 1, 2v + 1, v + 1000) e, para cor
Munsell, os inteiros de 0 a 10 — localizam uma região em que a classe é
restabelecida, e a bissecção entre o valor informado e a sonda aproxima a
fronteira. A busca alcança tanto as comparações diretas quanto os predicados
derivados (relação textural, saturação por bases, posição de horizonte), porque
quem decide é a reexecução do motor, e não a leitura do predicado.

Toda hipótese listada foi **verificada por reexecução** (compromisso (c)): o
perfil alterado deriva a classe registrada. Por isso nenhuma hipótese é
logicamente inválida, e uma falha do ordenador degrada a ordem, nunca a
corretude.

Limites desta versão, declarados:

* uma alteração por hipótese — divergências que exigem duas correções
  simultâneas não são explicadas;
* só atributos numéricos. Símbolo de horizonte (que viria do Inferidor),
  códigos categóricos (estrutura, cerosidade, transição), booleanos e limites
  de profundidade ficam fora;
* a busca encontra a fronteira **ao longo do segmento** entre o valor
  informado e a sonda; uma região de restabelecimento que nenhuma sonda toque
  não é encontrada.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Callable

from .avaliador import Derivacao, F, avaliar, classificar
from .perfil import Perfil, _derivados

#: Atributos analíticos — grandezas contínuas sujeitas a erro de registro.
ATRIBUTOS_ANALITICOS = (
    "ARGILA", "SILTE", "AREIA_GROS", "AREIA_FINA",
    "CA_TROC", "MG_TROC", "K_TROC", "NA_TROC", "H_TROC", "AL_TROC",
    "PH_AGUA", "PH_KCL", "C_ORG", "P_ASSIM", "TEOR_FE", "TEOR_P",
    "COND_ELETR", "EQUI_CACO3",
)

#: Valor e croma Munsell — inteiros de escala curta; decidem plíntico, glei
#: e A chernozêmico. A curadoria alterou um croma (`PE_045`, 6 → 5).
ATRIBUTOS_COR = (
    "COR_UMIDA_VALOR", "COR_UMIDA_CROMA", "COR_SECA_VALOR", "COR_SECA_CROMA",
    "COR_MOSQ_VALOR_1", "COR_MOSQ_CROMA_1",
)

#: Deslocamentos de separador decimal: o único tipo de erro numérico que o
#: registro de curadoria documenta (`PE_007`, MG_TROC 17 → 1,7). Ver
#: `nucleo/injecao.py` para a apuração.
FATORES_DECIMAIS = (10.0, 0.1, 100.0, 0.01, 1000.0, 0.001)

_ITERACOES_BISSECCAO = 24

#: Faixas fisicamente possíveis, as mesmas de sanidade do adaptador do acervo
#: (`tools/bdsolos_adapter.FAIXAS`). Um deslocamento decimal que leve o valor
#: para fora delas não é erro plausível e não conta como típico (I-2 da
#: auditoria de 2026-10-17: a argila do Bt do `PE_007` multiplicada por dez,
#: 4.000 g/kg, recebia τ = 1).
FAIXAS_FISICAS = {
    "ARGILA": (0, 1000), "SILTE": (0, 1000), "AREIA_GROS": (0, 1000),
    "AREIA_FINA": (0, 1000), "PH_AGUA": (0, 14), "PH_KCL": (0, 14),
    "C_ORG": (0, 600), "P_ASSIM": (0, 2000), "CA_TROC": (0, 100),
    "MG_TROC": (0, 100), "K_TROC": (0, 100), "NA_TROC": (0, 100),
    "AL_TROC": (0, 100), "H_TROC": (0, 100), "COND_ELETR": (0, 200),
    "EQUI_CACO3": (0, 1000), "TEOR_FE": (0, 1000),
}


def _plausivel(atributo: str, x: float) -> bool:
    lo, hi = FAIXAS_FISICAS.get(atributo, (0, math.inf))
    return lo <= x <= hi


@dataclass
class Hipotese:
    """Alteração de um atributo que restabelece a classe registrada."""

    atributo: str
    horizonte: str
    indice: int
    valor_informado: float
    valor_proposto: float
    #: Deslocamento decimal que também restabelece a classe, se houver
    #: (ex.: "÷10"). Alimenta o fator de tipicidade τ de §4.3.2.
    tipico: str | None = None
    escore: float = 0.0
    componentes: dict[str, float] = field(default_factory=dict)

    @property
    def delta(self) -> float:
        return self.valor_proposto - self.valor_informado

    @property
    def delta_relativo(self) -> float:
        """‖δ‖ de §4.3.2: |δ| / |v|, para comparar escalas distintas."""
        if self.valor_informado == 0:
            return math.inf
        return abs(self.delta) / abs(self.valor_informado)


@dataclass
class Explicacao:
    """O que o explicador devolve para um perfil divergente."""

    perfil: str
    classe_registrada: str
    classe_derivada: str | None
    alcancaveis: list[str]
    #: 1 — a condição da classe registrada é falsa;
    #: 2 — uma classe precedente foi concluída antes dela.
    origem: int
    #: Pontos de ruptura da origem 1 (folhas falhas da condição registrada),
    #: ou os predicados que sustentam a classe precedente, na origem 2.
    rupturas: list[Derivacao]
    hipoteses: list[Hipotese]


def valor_que_inverte(valor: float, operador: str, limiar: float) -> float:
    """Valor que satisfaz `valor <operador> limiar`, a partir de um que falha.

    Para comparação direta, o menor ajuste é a própria fronteira; nos
    predicados estritos, um passo de ponto flutuante além dela.
    """
    if operador in (">=", "<=", "=="):
        return float(limiar)
    if operador == ">" or operador == "!=":
        return math.nextafter(float(limiar), math.inf)
    if operador == "<":
        return math.nextafter(float(limiar), -math.inf)
    raise ValueError(f"operador não suportado: {operador!r}")


def divergente(perfil: Perfil, classe_registrada: str, chave=None) -> bool:
    """A classe registrada está fora do conjunto alcançável?"""
    res = classificar(perfil, _chave(chave))
    return classe_registrada not in _alcancavel(res)


def explicar(perfil: Perfil, classe_registrada: str, chave=None,
             sentinela: Callable[[Perfil, int, str], float] | None = None,
             pesos: tuple[float, float, float] = (1.0, 1.0, 1.0),
             ) -> Explicacao | None:
    """Explica a divergência; `None` se não houver divergência.

    `sentinela(perfil, indice, atributo)` devolve o escore de anomalia σ em
    [0, 1]; sem ele, σ = 0 e a ordem fica a cargo da magnitude e da
    tipicidade. `pesos` são (α, β, γ) de §4.3.2.
    """
    chave = _chave(chave)
    regra = next((r for r in chave if r.classe == classe_registrada), None)
    if regra is None:
        return None
    res = classificar(perfil, chave)
    if classe_registrada in _alcancavel(res):
        return None

    propria = avaliar(regra.condicao, perfil)
    if propria.valor is F:
        origem, rupturas = 1, propria.folhas_falhas()
    else:
        origem = 2
        rupturas = list(res.derivacao.filhos) if res.derivacao else []

    hipoteses = []
    for indice, h in enumerate(perfil.horizontes):
        for atributo in ATRIBUTOS_ANALITICOS + ATRIBUTOS_COR:
            v = h.get(atributo)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            hip = _buscar(perfil, indice, atributo, float(v),
                          classe_registrada, chave)
            if hip is not None:
                hipoteses.append(hip)

    for hip in hipoteses:
        sigma = sentinela(perfil, hip.indice, hip.atributo) if sentinela else 0.0
        pontuar(hip, sigma, pesos)
    hipoteses.sort(key=lambda h: (-h.escore, h.delta_relativo, h.atributo))

    return Explicacao(perfil.id_ponto, classe_registrada, res.classe,
                      list(res.alcancaveis), origem, rupturas, hipoteses)


def pontuar(hip: Hipotese, sigma: float,
            pesos: tuple[float, float, float]) -> float:
    """s(h) = α·σ + β·1/(1 + ‖δ‖) + γ·τ  (monografia, §4.3.2)."""
    alfa, beta, gama = pesos
    magnitude = 1.0 / (1.0 + hip.delta_relativo)
    tau = 1.0 if hip.tipico else 0.0
    hip.componentes = {"sigma": sigma, "magnitude": magnitude, "tau": tau}
    hip.escore = alfa * sigma + beta * magnitude + gama * tau
    return hip.escore


def verbalizar(exp: Explicacao, k: int = 3) -> str:
    """Explicação por preenchimento de modelo (§4.3.3), sem gerador de texto."""
    if exp.origem == 1:
        causa = (f"A condição de {exp.classe_registrada} é refutada pela norma"
                 f" nos dados informados.")
    else:
        causa = (f"A condição de {exp.classe_registrada} não é refutada, mas "
                 f"{exp.classe_derivada} a precede na chave e foi concluída antes.")
    linhas = [
        f"A ficha registra {exp.classe_registrada}; o núcleo deriva "
        f"{exp.classe_derivada or 'nenhuma classe conclusiva'}"
        + (f" (alcançáveis: {', '.join(exp.alcancaveis)})" if exp.alcancaveis else "")
        + ".",
        causa,
    ]
    for n in exp.rupturas[:3]:
        linhas.append(f"  · {n.rotulo}" + (f" — {n.detalhe}" if n.detalhe else ""))
    if not exp.hipoteses:
        linhas.append("Nenhuma alteração de um único atributo restabelece a "
                      "classe registrada; a divergência exige mais de uma "
                      "correção, ou recai sobre símbolo, código ou profundidade.")
        return "\n".join(linhas)
    for pos, h in enumerate(exp.hipoteses[:k], 1):
        tipo = (f"; compatível com deslocamento do separador decimal ({h.tipico})"
                if h.tipico else "")
        linhas.append(
            f"Hipótese {pos} (escore {h.escore:.2f}): {h.atributo}({h.horizonte}) "
            f"informado {h.valor_informado:g}; com {h.valor_proposto:.4g} a "
            f"classificação converge com a ficha{tipo}. "
            f"Escore de anomalia {h.componentes.get('sigma', 0):.2f}.")
    return "\n".join(linhas)


# ------------------------------------------------------------- internos -----

def _chave(chave):
    if chave is None:
        from .chave5 import CHAVE_5ED
        return CHAVE_5ED
    return chave


def _alcancavel(res) -> set[str]:
    return set(res.alcancaveis) | ({res.classe} if res.classe else set())


def alterar(perfil: Perfil, indice: int, atributo: str, valor) -> Perfil:
    """Cópia do perfil com um atributo trocado e os derivados recalculados.

    Sem o recálculo, uma hipótese sobre CA_TROC seria avaliada com a
    saturação por bases antiga — a hipótese mudaria o dado, e a regra leria
    o valor anterior.
    """
    alterado = copy.deepcopy(perfil)
    h = alterado.horizontes[indice]
    h.atributos[atributo] = valor
    for nome in ("SOMA_BASES", "CTC", "V_PERCENT", "ATIVIDADE_ARGILA"):
        h.atributos.pop(nome, None)
    h.atributos.update(_derivados(h))
    return alterado


def _deriva(perfil, indice, atributo, valor, alvo, chave) -> bool:
    return classificar(alterar(perfil, indice, atributo, valor), chave).classe == alvo


def _buscar(perfil, indice, atributo, v, alvo, chave) -> Hipotese | None:
    def ok(x):
        return _deriva(perfil, indice, atributo, x, alvo, chave)

    cor = atributo.startswith("COR_")
    tipico = None
    if cor:
        sondas = [float(x) for x in range(0, 11) if x != v]
    else:
        sondas = []
        for f_ in FATORES_DECIMAIS:
            if v != 0:
                sondas.append(v * f_)
        sondas += [0.0, v + 1.0, v * 2 + 1.0, v + 1000.0]

    funcionam = []
    for s in sondas:
        if s < 0 or s == v:
            continue
        if ok(s):
            funcionam.append(s)
    if not funcionam:
        return None

    melhor = None
    for s in funcionam:
        fronteira = _fronteira(ok, v, s, cor)
        if melhor is None or abs(fronteira - v) < abs(melhor - v):
            melhor = fronteira

    # τ (I-2, 2026-10-17): só conta como típico o deslocamento decimal que
    # restabelece a classe **e é fisicamente possível**. Antes bastava
    # restabelecer, e a argila do Bt do `PE_007` × 10 (4.000 g/kg) marcava
    # τ = 1. Exigir também que o deslocamento esteja do lado da fronteira
    # reportada foi tentado e descartado: na injeção "argila ÷ 10" do
    # `PE_001` (470 → 47), a correção verdadeira (× 10) fica do lado oposto
    # ao da fronteira mais próxima (47 → 0), e o τ de um erro decimal real
    # seria zerado. τ diz que o deslocamento também restabelece, não que a
    # fronteira reportada é ele.
    if not cor and v != 0:
        for s in funcionam:
            razao = s / v
            for f_, nome in ((10.0, "×10"), (0.1, "÷10"), (100.0, "×100"),
                             (0.01, "÷100"), (1000.0, "×1000"),
                             (0.001, "÷1000")):
                if (math.isclose(razao, f_, rel_tol=1e-9)
                        and _plausivel(atributo, s)):
                    tipico = nome
                    break
            if tipico:
                break
    return Hipotese(atributo, perfil.horizontes[indice].simbolo, indice,
                    v, melhor, tipico)


def _fronteira(ok, v: float, s: float, inteiro: bool) -> float:
    """Ponto mais próximo de `v` no segmento [v, s] que ainda restabelece.

    Invariante: `ok(dentro)` é verdadeiro. O valor devolvido foi testado.
    """
    if inteiro:
        passo = 1.0 if s > v else -1.0
        x = v + passo
        while (x - s) * passo <= 0:
            if ok(x):
                return x
            x += passo
        return s
    fora, dentro = v, s
    for _ in range(_ITERACOES_BISSECCAO):
        meio = (fora + dentro) / 2
        if meio == fora or meio == dentro:
            break
        if ok(meio):
            dentro = meio
        else:
            fora = meio
    return dentro
