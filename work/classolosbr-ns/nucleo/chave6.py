"""Chave do 1º nível categórico — SiBCS 6ª edição (SANTOS et al., 2025).

A ordem desta lista **é** a semântica: a primeira regra satisfeita determina a
classe. Não reordene sem ler o capítulo 4 da norma.

⚠️ A chave publicada não é a especificação completa. Ela própria declara trazer
"definições simplificadas" e manda reportar-se ao capítulo. A 6ª edição é mais
segura de transcrever que a 5ª — as exclusões que a 5ª enunciava na prosa
migraram para a posição na chave —, mas as condições continuam vindo do
capítulo. Cada regra registra em `fonte` de onde foi lida, e
`verificada_no_capitulo` diz se alguém cotejou.

⚠️ **O que foi de fato conferido no PDF da 6ª edição, em 2026-09-07**: a
sequência de precedência e o texto das treze cláusulas da chave (Cap. 4); as
definições de capítulo de Neossolos, Gleissolos, Cambissolos e Argissolos; o
limiar de 27 cmolc/kg que separa Ta de Tb; o limite de relação textural ≤ 1,5
do B latossólico; e a fórmula da relação textural B/A com os exemplos da
Tabela 1.1. **Não conferidos**, e portanto escritos a partir de conhecimento
de domínio: os patamares do A chernozêmico (cor, C orgânico, estrutura,
espessura), o limiar de 50% de saturação por bases, os 350 g/kg dos
Nitossolos, os 300 g/kg dos Vertissolos e o critério de mudança textural
abrupta. Cada um desses é um ponto onde o código pode divergir da norma sem
que nada acuse — conferir antes de qualquer uso que não seja exploratório.

**Recorte.** Cinco ordens estão implementadas a fundo (`no_recorte=True`):
Latossolos, Argissolos, Luvissolos, Espodossolos e Cambissolos. As outras oito
entram com regra de **triagem**: suficiente para preservar a precedência e para
refutar com segurança quando o perfil claramente não é daquela ordem, e
declaradamente insuficiente para afirmar a classe. Onde a triagem não pode
decidir, ela devolve indeterminado — e o Avaliador Parcial faz o resto.

⚠️ Cambissolos substituíram Neossolos no recorte em 2026-09-07: a realocação
dos Neossolos entre edições não altera desfecho, e a dos Cambissolos pode —
depende da leitura de "subjacente a" na definição dos Argissolos, ambiguidade
registrada e ainda não resolvida com a Embrapa.
"""

from __future__ import annotations

from .regras import (
    Booleano, Compara, Derivado, E, Existe, Nao, Ou, Pendente, Regra, Residual,
    Seletor,
)

CHAVE = "SiBCS 6ª ed. (2025), Cap. 4, chave das ordens, p. 121-123"


def _cap(numero: int, pagina: str) -> str:
    return f"SiBCS 6ª ed. (2025), Cap. {numero}, p. {pagina}"


CHAVE_6ED: list[Regra] = [

    # 1 -----------------------------------------------------------------------
    Regra(
        classe="ORGANOSSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="hístico"), fonte=CHAVE),
            Ou(partes=(
                Compara(atributo="ESPESSURA", operador=">=", limiar=40,
                        onde=Seletor(tipo="hístico"), unidade="cm",
                        fonte=CHAVE + " — critério (b)"),
                Pendente(motivo="hístico ≥ 20 cm sobre contato lítico ou "
                                "material com ≥ 90% de fragmentos",
                         fonte=CHAVE + " — critério (a)"),
                Pendente(motivo="hístico ≥ 60 cm com ≥ 75% de tecido vegetal",
                         fonte=CHAVE + " — critério (c)"),
            )),
        )),
        fonte=CHAVE, no_recorte=False,
        observacao="triagem: a espessura cumulativa nos primeiros 80 cm não é "
                   "somada — testa-se horizonte a horizonte",
    ),

    # 2 -----------------------------------------------------------------------
    Regra(
        classe="VERTISSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="vértico", inicio_ate_cm=100), fonte=CHAVE),
            Compara(atributo="ARGILA", operador=">=", limiar=300,
                    onde=Seletor(principal="A", inicio_ate_cm=20),
                    unidade="g/kg", fonte=CHAVE + " — requisito (a)"),
            Pendente(motivo="fendas verticais ≥ 1 cm atingindo 50 cm no "
                            "período seco", fonte=CHAVE + " — requisito (b)"),
            Pendente(motivo="COLE ≥ 0,06 em área irrigada ou mal drenada",
                     fonte=CHAVE + " — requisito (d)"),
        )),
        fonte=CHAVE, no_recorte=False,
    ),

    # 3 -----------------------------------------------------------------------
    Regra(
        classe="ESPODOSSOLO",
        condicao=Existe(
            onde=Seletor(tipo="B espódico"),
            imediatamente_abaixo_de=("E", "A", "H"),
            fonte=CHAVE,
        ),
        fonte=_cap(8, "175"), verificada_no_capitulo=True, no_recorte=True,
        observacao="a 6ª edição acrescentou o hístico < 40 cm às posições "
                   "admitidas acima do B espódico",
    ),

    # 4 -----------------------------------------------------------------------
    Regra(
        classe="PLANOSSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="B textural"),
                   imediatamente_abaixo_de=("A", "E"), fonte=CHAVE),
            Derivado(predicado="mudança textural abrupta",
                     fonte=_cap(15, "259")),
            Pendente(motivo="estrutura prismática/colunar ou em blocos com "
                            "permeabilidade lenta, que define o B plânico",
                     fonte=_cap(15, "259")),
        )),
        fonte=CHAVE, no_recorte=False,
        observacao="triagem: sem o critério estrutural, um Planossolo real "
                   "sai como indeterminado — nunca como outra ordem",
    ),

    # 5 -----------------------------------------------------------------------
    Regra(
        classe="PLINTOSSOLO",
        condicao=Ou(partes=(
            Existe(onde=Seletor(tipo="plíntico", inicio_ate_cm=40), fonte=CHAVE),
            Existe(onde=Seletor(tipo="concrecionário", inicio_ate_cm=40),
                   fonte=CHAVE),
            Existe(onde=Seletor(tipo="litoplíntico", inicio_ate_cm=40),
                   fonte=CHAVE),
            Derivado(predicado="plíntico até 200 cm em posição diagnóstica (6ª ed.)",
                     fonte=CHAVE + " — condição (b)"),
        )),
        fonte=CHAVE, no_recorte=False,
    ),

    # 6 -----------------------------------------------------------------------
    Regra(
        classe="GLEISSOLO",
        condicao=E(partes=(
            Derivado(predicado="glei em posição diagnóstica (6ª ed.)", fonte=_cap(9, "183")),
            Nao(parte=Existe(onde=Seletor(tipo="B diagnóstico")),
                fonte=_cap(9, "183") + " — requisito (a)"),
            Derivado(predicado="sem textura areia exclusiva até 200 cm (6ª ed.)",
                     fonte=_cap(9, "183") + " — requisito (d)"),
        )),
        fonte=_cap(9, "183"), verificada_no_capitulo=True, no_recorte=False,
        observacao="simplificação declarada: a norma proíbe B diagnóstico "
                   "*acima* do glei; aqui proíbe-se em todo o perfil",
    ),

    # 7 -----------------------------------------------------------------------
    Regra(
        classe="LATOSSOLO",
        condicao=Existe(
            onde=Seletor(tipo="B latossólico"),
            imediatamente_abaixo_de=("A",),
            fonte=CHAVE,
        ),
        fonte=_cap(10, "203"), verificada_no_capitulo=True, no_recorte=True,
    ),

    # 8 -----------------------------------------------------------------------
    Regra(
        classe="CHERNOSSOLO",
        condicao=E(partes=(
            Derivado(predicado="horizonte A chernozêmico", fonte=_cap(7, "167")),
            Ou(partes=(
                E(partes=(
                    Existe(onde=Seletor(tipo="B incipiente")),
                    Compara(atributo="ATIVIDADE_ARGILA", operador=">=", limiar=27,
                            onde=Seletor(tipo="B incipiente"),
                            unidade="cmolc/kg de argila"),
                    Compara(atributo="V_PERCENT", operador=">=", limiar=50,
                            onde=Seletor(tipo="B incipiente"), unidade="%"),
                )),
                E(partes=(
                    Existe(onde=Seletor(tipo="B textural")),
                    Compara(atributo="ATIVIDADE_ARGILA", operador=">=", limiar=27,
                            onde=Seletor(tipo="B textural"),
                            unidade="cmolc/kg de argila"),
                    Compara(atributo="V_PERCENT", operador=">=", limiar=50,
                            onde=Seletor(tipo="B textural"), unidade="%"),
                )),
                Pendente(motivo="horizonte cálcico, petrocálcico ou caráter "
                                "carbonático seguido de contato lítico",
                         fonte=CHAVE),
            )),
        )),
        fonte=CHAVE, no_recorte=False,
    ),

    # 9 -----------------------------------------------------------------------
    Regra(
        classe="LUVISSOLO",
        condicao=E(partes=(
            Ou(partes=(
                Existe(onde=Seletor(tipo="B textural"),
                       imediatamente_abaixo_de=("A", "E"),
                       fonte=_cap(3, "105") + " — Definição: 'imediatamente "
                                               "abaixo'"),
                E(partes=(
                    Existe(onde=Seletor(tipo="B textural", inicio_ate_cm=200),
                           fonte=_cap(11, "221") + " — 'nos primeiros 200 "
                                                   "cm [...] subjacente a'"),
                    Pendente(motivo="B textural nos primeiros 200 cm, mas não "
                                    "imediatamente abaixo do A ou E: a 6ª edição "
                                    "não decide — 'subjacente a' na chave e no "
                                    "Cap. 11 (p. 221), 'imediatamente abaixo' na "
                                    "Definição do Cap. 3 (p. 105)",
                             fonte=_cap(11, "221")),
                )),
            )),
            Compara(atributo="ATIVIDADE_ARGILA", operador=">=", limiar=27,
                    onde=Seletor(tipo="B textural", seccao_controle_cm=100),
                    agregacao="maior parte",
                    unidade="cmolc/kg de argila",
                    fonte=_cap(11, "221") + " — argila de atividade alta na "
                                            "maior parte dos primeiros 100 cm do B"),
            Compara(atributo="V_PERCENT", operador=">=", limiar=50,
                    onde=Seletor(tipo="B textural", seccao_controle_cm=100),
                    agregacao="maior parte", unidade="%",
                    fonte=_cap(11, "221") + " — saturação por bases alta"),
        )),
        fonte=_cap(11, "221"), verificada_no_capitulo=True, no_recorte=True,
        observacao="a agregação 'maior parte' é ponderada pela espessura dos "
                   "horizontes B texturais. O empate exato devolve "
                   "indeterminado — é o caso `GeoTab_RN_007_Acu`, a lacuna da "
                   "norma que o SmartSolos identificou e a 6ª edição creditou. "
                   "⚠️ Posição do Bt (2026-10-15): mesma inconsistência dos "
                   "Argissolos — 'subjacente a' na chave e no Cap. 11, "
                   "'imediatamente abaixo' na Definição do Cap. 3. Adjacente → "
                   "V; só nos primeiros 200 cm → I; a proposta do CE de 2026 "
                   "não trata dos Luvissolos neste ponto",
    ),

    # 10 ----------------------------------------------------------------------
    Regra(
        classe="NITOSSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="B nítico"), fonte=CHAVE),
            Compara(atributo="ARGILA", operador=">=", limiar=350,
                    onde=Seletor(principal="A"), unidade="g/kg",
                    fonte=CHAVE + " — argila inclusive no A"),
            Pendente(motivo="ausência de policromia nos primeiros 150 cm",
                     fonte=_cap(13, "243")),
        )),
        fonte=CHAVE, no_recorte=False,
    ),

    # 11 ----------------------------------------------------------------------
    Regra(
        classe="ARGISSOLO",
        condicao=E(partes=(
            Ou(partes=(
                Existe(onde=Seletor(tipo="B textural"),
                       imediatamente_abaixo_de=("A", "E"),
                       fonte=_cap(3, "97") + " — Definição: 'imediatamente abaixo'"),
                E(partes=(
                    Existe(onde=Seletor(tipo="B textural", inicio_ate_cm=200),
                           fonte=_cap(5, "125") + " — 'subjacente a [...] nos "
                                                  "primeiros 200 cm'"),
                    Pendente(motivo="B textural nos primeiros 200 cm, mas não "
                                    "imediatamente abaixo do A ou E: a 6ª edição "
                                    "não decide — 'subjacente a' no Cap. 5 (p. 125), "
                                    "'imediatamente abaixo' na Definição do Cap. 3 "
                                    "(p. 97) e prevalência do primeiro horizonte "
                                    "diagnóstico de subsuperfície no pressuposto (b) "
                                    "da chave (p. 120)",
                             fonte=_cap(5, "125")),
                )),
            )),
            Derivado(predicado="requisitos (a) e (b) da Definição dos "
                               "Argissolos (6ª ed.)",
                     fonte=_cap(3, "97") + " — plíntico, concrecionário, "
                                           "litoplíntico e glei não acima nem "
                                           "coincidentes com o topo do Bt"),
            Residual(fonte=CHAVE),
        )),
        fonte=_cap(5, "125"), verificada_no_capitulo=True, no_recorte=True,
        observacao="⚠️ **A 6ª edição é internamente inconsistente aqui** "
                   "(conferido nos PDFs em 2026-10-12). O Cap. 5 diz 'B textural "
                   "**subjacente a** horizonte A ou E, nos primeiros 200 cm'; a "
                   "Definição do Cap. 3 manteve '**imediatamente abaixo**'; o "
                   "item da chave não exige posição; e o pressuposto (b) da "
                   "chave dá prevalência ao primeiro horizonte diagnóstico de "
                   "subsuperfície. Até 2026-10-15 a regra adotava sem declarar a "
                   "leitura do item da chave (sem adjacência e sem o limite de "
                   "200 cm): o perfil A–Bi–Bt saía ARGISSOLO concluído, e a "
                   "Camada de Versão reportava como diferença normativa o que é "
                   "ambiguidade. Agora: B textural imediatamente abaixo do A ou E "
                   "→ V (todas as leituras concordam); só nos primeiros 200 cm → "
                   "**I** (a norma não decide); fora disso → F. A proposta de "
                   "atualização do CE (Santos et al., 2026, p. 39) mantém "
                   "'imediatamente abaixo' na Definição e acrescenta os 200 cm "
                   "— indica a leitura com adjacência, mas é proposta para "
                   "teste, não norma: a indeterminação fica (decisão de "
                   "2026-10-15)",
    ),

    # 12 ----------------------------------------------------------------------
    Regra(
        classe="CAMBISSOLO",
        condicao=Existe(
            onde=Seletor(tipo="B incipiente"),
            imediatamente_abaixo_de=("A", "H"),
            fonte=CHAVE,
        ),
        fonte=_cap(6, "149"), verificada_no_capitulo=True, no_recorte=True,
        observacao="a 6ª edição suprimiu do capítulo a frase que excluía "
                   "plintita, glei e vértico em posição diagnóstica — a "
                   "exclusão passou a ser feita pela posição na chave",
    ),

    # 13 ----------------------------------------------------------------------
    Regra(
        classe="NEOSSOLO",
        condicao=E(partes=(
            Derivado(predicado="sem horizonte B diagnóstico", fonte=_cap(12, "227")),
            Residual(fonte=CHAVE),
        )),
        fonte=_cap(12, "227"), verificada_no_capitulo=True, no_recorte=False,
        observacao="classe residual na 6ª edição. Na 5ª era testada em 2º "
                   "lugar com lista de exclusões no capítulo — mesmo desfecho, "
                   "forma diferente (verificado em 2026-09-07)",
    ),
]


def cobertura() -> str:
    """Relatório do que está implementado, para não confundir escopo com fé."""
    linhas = ["| # | Classe | Recorte | Capítulo conferido | Pendências |",
              "|---|---|---|---|---|"]
    for i, regra in enumerate(CHAVE_6ED, 1):
        pendentes = _conta_pendentes(regra.condicao)
        linhas.append(
            f"| {i} | {regra.classe} | "
            f"{'sim' if regra.no_recorte else 'triagem'} | "
            f"{'sim' if regra.verificada_no_capitulo else 'não'} | "
            f"{pendentes or '—'} |"
        )
    return "\n".join(linhas)


def _conta_pendentes(condicao) -> int:
    if isinstance(condicao, Pendente):
        return 1
    if isinstance(condicao, (E, Ou)):
        return sum(_conta_pendentes(p) for p in condicao.partes)
    if isinstance(condicao, Nao):
        return _conta_pendentes(condicao.parte)
    return 0
