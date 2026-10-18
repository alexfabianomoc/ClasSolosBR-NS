"""Gerador de erros injetados (monografia, §3.4 e §3.5, mitigação 5).

Os tipos e as magnitudes vêm do **registro de curadoria** do conjunto curado
(campo `CURADORIA`), e não de suposição. Apuração de 2026-10-15, lendo os 67
registros que não dizem "Nenhuma alteração":

* **separador decimal deslocado** — um caso: `GeoTab_PE_007_Escada`,
  "MG_TROC estava como 17, mas é 1.7" (informado = 10 × verdadeiro). É o
  único erro numérico de atributo analítico documentado, e é o que se injeta,
  nas duas direções (×10 e ÷10), sobre os atributos analíticos;
* **soma de parcelas num único campo** — `PE_004` e `PE_014` (Ca + Mg). A
  correção altera dois atributos, fora do alcance de hipóteses de alteração
  única; não injetado;
* arredondamento (`RN_031`), sentinela de profundidade aberta (`RN_012`,
  `RN_029`), sinal do limite superior (`PE_002`), valor ausente completado
  (`PE_020`, `PE_028`) e códigos de cerosidade e croma (`PE_045`) — não são
  erro numérico de atributo analítico ou recaem sobre profundidade e códigos;
  não injetados.

⚠️ **Unidade trocada e dígito omitido**, que a §3.4 e a §4.3.1 citavam como
tipos documentados até 2026-10-16 (texto corrigido nessa data), **não
aparecem no registro**. Injetá-los seria suposição,
contra a mitigação 5; ficam de fora até que uma fonte os documente.

Só se retêm as injeções que tornam a classe do perfil limpo **inalcançável**
(divergência no sentido de §4.3.1). Injeções que só tornam o resultado não
conclusivo, mantendo a classe alcançável, são incompletude e são contadas à
parte.
"""

from __future__ import annotations

from dataclasses import dataclass

from .avaliador import classificar
from .explicador import ATRIBUTOS_ANALITICOS, alterar
from .perfil import Perfil

#: (fator, rótulo). O fator multiplica o valor verdadeiro.
FATORES = ((10.0, "×10"), (0.1, "÷10"))


@dataclass
class Injecao:
    original: Perfil
    perfil: Perfil
    classe: str
    indice: int
    atributo: str
    valor_original: float
    valor_injetado: float
    tipo: str


@dataclass
class Apuracao:
    injecoes: list[Injecao]
    #: Tentativas por desfecho: "divergência", "incompletude", "sem efeito".
    desfechos: dict[str, int]
    perfis_elegiveis: int


def gerar(perfis: list[Perfil], chave=None,
          atributos=ATRIBUTOS_ANALITICOS, fatores=FATORES) -> Apuracao:
    """Todas as injeções de um atributo × fator, sobre perfis conclusivos."""
    injecoes: list[Injecao] = []
    desfechos = {"divergência": 0, "incompletude": 0, "sem efeito": 0}
    elegiveis = 0
    for p in perfis:
        limpo = classificar(p, chave)
        if not limpo.conclusivo:
            continue
        elegiveis += 1
        for i, h in enumerate(p.horizontes):
            for a in atributos:
                v = h.get(a)
                if isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0:
                    continue
                for fator, tipo in fatores:
                    q = alterar(p, i, a, float(v) * fator)
                    r = classificar(q, chave)
                    alcancaveis = set(r.alcancaveis) | ({r.classe} if r.classe else set())
                    if limpo.classe not in alcancaveis:
                        desfechos["divergência"] += 1
                        injecoes.append(Injecao(p, q, limpo.classe, i, a,
                                                float(v), float(v) * fator, tipo))
                    elif r.conclusivo and r.classe == limpo.classe:
                        desfechos["sem efeito"] += 1
                    else:
                        desfechos["incompletude"] += 1
    return Apuracao(injecoes, desfechos, elegiveis)
