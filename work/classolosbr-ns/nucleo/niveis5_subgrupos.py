"""4º nível categórico (subgrupos) das cinco ordens do recorte — SiBCS 5ª ed.

Os 448 subgrupos (`dados/subgrupos5.json`, extraídos do PDF por
`subgrupos_texto.py`) usam apenas **100 definições distintas**. Cada uma é
traduzida em condição **uma vez**, na tabela `TRADUCAO`, na ordem em que
aparecem no texto; cada entrada traz as palavras que a definição tem de
conter, e `verificar_traducao()` falha se o texto e a tradução se
desencontrarem. A precedência dentro de cada grande grupo é a do texto.

O que o contrato não traz vira `Pendente` com o motivo — fragipã, caráter
dúrico, espódico, plânico, rúbrico, policromia e a morfologia de B
latossólico em B incipiente. O efeito é o do resto do núcleo: o subgrupo
fica alcançável, e o "típico" só conclui quando todos os anteriores são
refutados.

Leituras declaradas (⚠️), além das de `predicados_subgrupos`:

* caráter plíntico lido no sufixo `f`; contato lítico no horizonte R;
  horizonte A antrópico no booleano ATIVIDADES_HUMANAS; materiais primários
  alteráveis (cambissólicos) no booleano MATERIAIS_PRIMARIOS; caráter
  retrátil em qualquer horizonte B;
* "em posição não diagnóstica para Gleissolos/Plintossolos/Vertissolos" não
  se testa de novo: o 1º nível já excluiu a posição diagnóstica.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import horizontes
from .niveis5 import (ATE_100, ATE_150, B100, GRANDES_GRUPOS, algum,
                      carbonatico, mp, normaliza)
from .predicados_subgrupos import PREDICADOS_SUBGRUPOS
from .regras import (Booleano, Compara, Derivado, E, Existe, Ou, Pendente,
                     Regra, Residual, Seletor)

horizontes.PREDICADOS.update(PREDICADOS_SUBGRUPOS)

DADOS = Path(__file__).parent / "dados" / "subgrupos5.json"
ATE_50 = Seletor(inicio_ate_cm=50)
ATE_80 = Seletor(inicio_ate_cm=80)
ATE_200 = Seletor(inicio_ate_cm=200)


def D(nome):
    return Derivado(predicado=nome)


def P(motivo):
    return Pendente(motivo=motivo)


MTA = D("mudança textural abrupta")
AHUM = D("horizonte A húmico")
C10_80 = D("carbono ≥ 10 g/kg até 80 cm")
AREN50 = D("textura arenosa da superfície até 50–100 cm")
AREN100 = D("textura arenosa da superfície até 100–200 cm")
ESP_AREN50 = D("arenosa até o B espódico a 50–100 cm")
ESP_AREN100 = D("arenosa até o B espódico a 100–200 cm")
DURICO = P("caráter dúrico (cimentação) não está no contrato")
FRAGIPA = P("fragipã não está no contrato")
ESPODICO = P("caráter espódico não está no contrato")
PLANICO = P("caráter plânico não está no contrato")
RUBRICO = P("caráter rúbrico não está no contrato")
LATOSSOLICO_CAMB = P("B incipiente com morfologia de B latossólico: comparação morfológica fora do contrato")
PLACICO = Booleano(atributo="PLACICO_TOPO", onde=ATE_150)
PLINT150 = D("caráter ou horizonte plíntico até 150 cm")
PLINT200 = D("caráter ou horizonte plíntico até 200 cm")
PETRO150 = D("concrecionário ou litoplíntico até 150 cm")
PETRO200 = D("concrecionário ou litoplíntico até 200 cm")
LATO_BT = D("B latossólico abaixo do B textural até 150 cm")
REDOX50 = Booleano(atributo="REDOXICO", onde=ATE_50)
REDOX50_150 = D("caráter redóxico entre 50 e 150 cm")
SOLOD150 = algum("SOLODICO", ">=", 1, ATE_150, "")
SOLOD100 = algum("SOLODICO", ">=", 1, ATE_100, "")
SALINO150 = algum("SALINO", ">=", 1, ATE_150, "")
SALINO100 = algum("SALINO", ">=", 1, ATE_100, "")
HIPOCARB100 = algum("HIPOCARBONATICO", ">=", 1, ATE_100, "")
HIPOCARB150 = algum("HIPOCARBONATICO", ">=", 1, ATE_150, "")
GLEI150 = Existe(onde=Seletor(tipo="glei", inicio_ate_cm=150))
GLEI80 = Existe(onde=Seletor(tipo="glei", inicio_ate_cm=80))
VERT150 = Existe(onde=Seletor(tipo="vértico", inicio_ate_cm=150))
VERT100 = Existe(onde=Seletor(tipo="vértico", inicio_ate_cm=100))
ANTROPICO = Booleano(atributo="ATIVIDADES_HUMANAS", onde=Seletor(principal="A"))
CAMB150 = Booleano(atributo="MATERIAIS_PRIMARIOS", onde=Seletor(principal="B", inicio_ate_cm=150))
CAMB200 = Booleano(atributo="MATERIAIS_PRIMARIOS", onde=Seletor(principal="B", inicio_ate_cm=200))
LEPTOFRAG = D("contato lítico fragmentário entre 50 e 100 cm")
LEPTICO = D("contato lítico entre 50 e 100 cm")
FRAG50 = D("contato lítico fragmentário até 50 cm")
LITICO50 = D("contato lítico até 50 cm")
SAPRO = D("Cr sem contato lítico até 100 cm")
NITOSS = E(partes=(D("cerosidade nítica no B"),
                   Ou(partes=(D("relação textural > 1,5"), P("policromia não está no contrato")))))
SOMBR150 = Booleano(atributo="SOMBRICO", onde=ATE_150)
CHERNO20 = E(partes=(D("horizonte A chernozêmico"),
                     mp("ATIVIDADE_ARGILA", ">=", 20, "", "cmolc/kg de argila")))
CHERNO_GT20 = E(partes=(D("horizonte A chernozêmico"),
                        mp("ATIVIDADE_ARGILA", ">", 20, "", "cmolc/kg de argila")))
LUVISS = E(partes=(mp("ATIVIDADE_ARGILA", ">=", 20, "", "cmolc/kg de argila"),
                   mp("SOMA_BASES", ">=", 5.0, "", "cmolc/kg")))
ARGILUV = E(partes=(D("relação textural ≥ 1,4"), D("estrutura argilúvica no B")))
ARGISS = Ou(partes=(D("relação textural ≥ 1,4"), D("blocos moderada e cerosidade no B")))
ORGANOSS = Existe(onde=Seletor(tipo="hístico"))
EUTRICO = Compara(atributo="EUTRICO", operador=">=", limiar=1,
                  onde=Seletor(seccao_controle_cm=100), agregacao="maior parte")
RETRAT = Booleano(atributo="RETRATIL", onde=Seletor(principal="B"))
PSAMIT = Compara(atributo="ARGILA", operador="<", limiar=200,
                 onde=Seletor(seccao_controle_cm=150), agregacao="maior parte", unidade="g/kg")
CARB150 = carbonatico(ATE_150, "")
RES = Residual()


def e(*partes):
    return E(partes=partes)


#: (palavras que a definição contém, condição) — na ordem das 100 definições.
TRADUCAO = [
    (("mudança textural abrupta",), MTA),                                             # 000
    (("A húmico", "80 cm"), e(AHUM, C10_80)),                                          # 001
    (("A húmico",), AHUM),                                                             # 002
    (("Outros solos",), RES),                                                          # 003
    (("Outros solos",), RES),                                                          # 004
    (("textura arenosa", "50 cm", "100 cm"), AREN50),                                  # 005
    (("abrupta", "dúrico"), e(MTA, DURICO)),                                           # 006
    (("abrupta", "fragipã"), e(MTA, FRAGIPA)),                                         # 007
    (("dúrico",), DURICO),                                                             # 008
    (("fragipã",), FRAGIPA),                                                           # 009
    (("plíntico", "150 cm"), PLINT150),                                                # 010
    (("B latossólico abaixo", "B textural"), LATO_BT),                                 # 011
    (("Cr", "redóxico", "abrupta"), e(SAPRO, REDOX50_150, MTA)),                       # 012
    (("redóxico dentro de 50 cm",), REDOX50),                                          # 013
    (("redóxico", "maior que 50 cm"), REDOX50_150),                                    # 014
    (("abrupta", "solódico"), e(MTA, SOLOD150)),                                       # 015
    (("arenosa", "fragipã"), e(AREN50, FRAGIPA)),                                      # 016
    (("abrupta", "fragipã", "espódico"), e(MTA, FRAGIPA, ESPODICO)),                   # 017
    (("abrupta", "concrecionário"), e(MTA, PETRO150)),                                 # 018
    (("abrupta", "plíntico"), e(MTA, PLINT150)),                                       # 019
    (("abrupta", "espódico"), e(MTA, ESPODICO)),                                       # 020
    (("fragipã", "plácico"), e(FRAGIPA, PLACICO)),                                     # 021
    (("fragipã", "plíntico"), e(FRAGIPA, PLINT150)),                                   # 022
    (("fragipã", "espódico"), e(FRAGIPA, ESPODICO)),                                   # 023
    (("fragipã", "plânico"), e(FRAGIPA, PLANICO)),                                     # 024
    (("caráter espódico",), ESPODICO),                                                 # 025
    (("caráter plânico",), PLANICO),                                                   # 026
    (("horizonte glei", "150 cm"), GLEI150),                                           # 027
    (("A antrópico", "plíntico"), e(ANTROPICO, PLINT150)),                             # 028
    (("4%", "minerais alteráveis", "150 cm"), CAMB150),                                # 029
    (("lítico fragmentário", "maior que 50 cm"), LEPTOFRAG),                           # 030
    (("contato lítico", "maior que 50 cm"), LEPTICO),                                  # 031
    (("plíntico", "plânico", "solódico"), e(PLINT150, PLANICO, SOLOD150)),             # 032
    (("solódico", "150 cm"), SOLOD150),                                                # 033
    (("semelhante aos Nitossolos",), NITOSS),                                          # 034
    (("sômbrico",), SOMBR150),                                                         # 035
    (("textura arenosa", "maior que 100 cm"), AREN100),                                # 036
    (("Cr", "abrupta"), e(SAPRO, MTA)),                                                # 037
    (("semelhante aos Nitossolos", "chernozêmico"), e(NITOSS, CHERNO20)),              # 038
    (("Cr (brando)", "ausência de contato lítico"), SAPRO),                            # 039
    (("abrupta", "plíntico", "solódico"), e(MTA, PLINT150, SOLOD150)),                 # 040
    (("abrupta", "A antrópico", "B latossólico"), e(MTA, ANTROPICO, LATO_BT)),         # 041
    (("abrupta", "chernozêmico"), e(MTA, CHERNO20)),                                   # 042
    (("≥ 20", "valor S"), LUVISS),                                                     # 043
    (("chernozêmico", "≥ 20"), CHERNO20),                                              # 044
    (("abrupta", "arenosa", "maior que 100 cm"), e(MTA, AREN100)),                     # 045
    (("abrupta", "arenosa", "50 cm"), e(MTA, AREN50)),                                 # 046
    (("concrecionário", "150 cm"), PETRO150),                                          # 047
    (("abrupta", "lítico fragmentário"), e(MTA, LEPTOFRAG)),                           # 048
    (("abrupta", "contato lítico"), e(MTA, LEPTICO)),                                  # 049
    (("abrupta", "chernozêmico", "Cr"), e(MTA, CHERNO20, SAPRO)),                      # 050
    (("abrupta", "plânico"), e(MTA, PLANICO)),                                         # 051
    (("B incipiente", "B latossólico"), LATOSSOLICO_CAMB),                             # 052
    (("vértico", "150 cm"), VERT150),                                                  # 053
    (("salino", "glei"), e(SALINO150, GLEI150)),                                       # 054
    (("salino", "150 cm"), SALINO150),                                                 # 055
    (("solódico", "150 cm"), SOLOD150),                                                # 056
    (("lítico fragmentário dentro de 50 cm",), FRAG50),                                # 057
    (("contato lítico dentro de 50 cm",), LITICO50),                                   # 058
    (("hipocarbonático", "contato lítico"), e(HIPOCARB100, LEPTICO)),                  # 059
    (("argilúvico",), ARGILUV),                                                        # 060
    (("plíntico", "solódico"), e(PLINT150, SOLOD150)),                                 # 061
    (("chernozêmico", "> 20"), CHERNO_GT20),                                           # 062
    (("hístico",), ORGANOSS),                                                          # 063
    (("arenosa", "B espódico", "maior que 100 cm"), ESP_AREN100),                      # 064
    (("arenosa", "B espódico", "50 cm"), ESP_AREN50),                                  # 065
    (("dúrico",), DURICO),                                                             # 066
    (("Hiperespessos",), RES),                                                         # 067
    (("fragipã",), FRAGIPA),                                                           # 068
    (("Hiperespessos",), RES),                                                         # 069
    (("Hiperespessos",), RES),                                                         # 070
    (("carbonático", "cálcico"), CARB150),                                             # 071
    (("êutrico", "arenosa"), e(EUTRICO, ESP_AREN50)),                                  # 072
    (("êutrico",), EUTRICO),                                                           # 073
    (("arenosa", "B espódico", "50 cm"), ESP_AREN50),                                  # 074
    (("rúbrico",), RUBRICO),                                                           # 075
    (("concrecionário", "200 cm"), PETRO200),                                          # 076
    (("plíntico", "200 cm"), PLINT200),                                                # 077
    (("1,4", "blocos moderad"), ARGISS),                                               # 078
    (("A antrópico",), ANTROPICO),                                                     # 079
    (("argila inferior a 200",), PSAMIT),                                              # 080
    (("concrecionário", "plíntico", "200 cm"), e(PETRO200, PLINT200)),                 # 081
    (("materiais primários", "200 cm"), CAMB200),                                      # 082
    (("retrátil",), RETRAT),                                                           # 083
    (("materiais primários", "200 cm"), CAMB200),                                      # 084
    (("materiais primários", "200 cm"), CAMB200),                                      # 085
    (("materiais primários", "200 cm"), CAMB200),                                      # 086
    (("plíntico", "200 cm"), PLINT200),                                                # 087
    (("vértico", "100 cm"), VERT100),                                                  # 088
    (("plânico", "100 cm"), PLANICO),                                                  # 089
    (("concrecionário", "150 cm"), PETRO150),                                          # 090
    (("materiais primários", "150 cm"), CAMB150),                                      # 091
    (("salino", "100 cm"), SALINO100),                                                 # 092
    (("vértico", "solódico"), e(VERT100, SOLOD100)),                                   # 093
    (("solódico", "plânico"), e(SOLOD100, PLANICO)),                                   # 094
    (("solódico", "100 cm"), SOLOD100),                                                # 095
    (("plânico", "vértico"), e(PLANICO, VERT100)),                                     # 096
    (("hipocarbonático", "150 cm"), HIPOCARB150),                                      # 097
    (("fragipã", "plíntico"), e(FRAGIPA, PLINT150)),                                   # 098
    (("horizonte glei", "80 cm"), GLEI80),                                             # 099
]


def _registros():
    return json.loads(DADOS.read_text(encoding="utf-8"))


def definicoes_em_ordem() -> list[str]:
    vistas = []
    for r in _registros():
        if r["definicao"] not in vistas:
            vistas.append(r["definicao"])
    return vistas


def verificar_traducao() -> list[str]:
    """Problemas entre o texto das definições e a tabela; vazio = coerente."""
    problemas = []
    defs = definicoes_em_ordem()
    if len(defs) != len(TRADUCAO):
        problemas.append(f"{len(defs)} definições para {len(TRADUCAO)} traduções")
    for i, (texto, (palavras, _)) in enumerate(zip(defs, TRADUCAO)):
        faltam = [p for p in palavras if p not in texto]
        if faltam:
            problemas.append(f"D{i:03d}: faltam {faltam} em {texto[:80]!r}")
    return problemas


def _chave_do_gg(texto_gg: str):
    alvo = normaliza(texto_gg)
    for (ordem, sub), regras in GRANDES_GRUPOS.items():
        for rg in regras:
            if normaliza(f"{ordem} {sub} {rg.classe}") == alvo:
                return (ordem, sub, rg.classe)
    return None


def _montar():
    condicao_de = {texto: cond for texto, (_, cond) in zip(definicoes_em_ordem(), TRADUCAO)}
    tabela: dict[tuple[str, str, str], list[Regra]] = {}
    sem_chave = set()
    for r in _registros():
        chave = _chave_do_gg(r["grande_grupo"] or "")
        if chave is None:
            sem_chave.add(r["grande_grupo"])
            continue
        nome = r["nome"]
        resto = nome[len(r["grande_grupo"]):].strip() if nome.startswith(r["grande_grupo"]) \
            else nome.split()[-1]
        fonte = f"SiBCS 5ª ed. (2018), p. {r['pagina']} — {r['texto']}"
        tabela.setdefault(chave, []).append(
            Regra(resto, condicao_de[r["definicao"]], fonte=fonte))
    return {k: tuple(v) for k, v in tabela.items()}, sem_chave


SUBGRUPOS, GG_SEM_CHAVE = _montar()
