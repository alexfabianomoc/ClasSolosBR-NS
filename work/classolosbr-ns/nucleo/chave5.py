"""Chave do 1º nível categórico — SiBCS 5ª edição (SANTOS et al., 2018).

Esta é a base de regras do **ClasSolosBR-NS5**: a edição que o sistema de
referência ([[smartsolos-expert]]) implementa em produção e sob a qual os dois
acervos disponíveis ([[bdsolos-redape-embrapa]] e [[pykka7-smartsolos-dataset]])
foram rotulados. A chave da 6ª edição continua no núcleo, em `chave6.py`, e
serve o módulo versão-consciente (M3), que classifica o mesmo perfil sob as
duas e compara.

A ordem desta lista **é** a semântica: a primeira regra satisfeita determina a
classe. A sequência da 5ª edição difere da 6ª em três realocações —
Neossolos 2ª (era residual na 6ª), Cambissolos 9ª e Plintossolos 10ª.

⚠️ **A chave publicada não é a especificação completa, e na 5ª edição isso é
mais grave que na 6ª.** A 5ª enuncia na prosa dos capítulos exclusões que a 6ª
passou a fazer pela posição na chave. Transcrever a chave da 5ª sozinha produz
um sistema que reproduz a chave e diverge da norma — ver
[[diff-sibcs-5ed-6ed-classolosbr]] §1. Onde chave e capítulo divergem, **este
módulo segue o capítulo**, e a divergência fica registrada em `observacao`.

## Princípio de comparabilidade com `chave6.py`

Esta base foi escrita para diferir da chave da 6ª edição **somente onde as duas
edições diferem**. A razão é metodológica: o M3 mede divergência entre edições,
e qualquer assimetria de modelagem introduzida aqui apareceria na saída como se
fosse diferença de norma. Critérios que ambas as edições enunciam e que
`chave6.py` não codifica (a atividade da argila dos Argissolos, o "exceto A
chernozêmico" dos Luvissolos) seguem **não codificados aqui também** — cada um
está registrado em `observacao`, com o motivo.

As diferenças deliberadas em relação a `chave6.py` são cinco, e só estas:

1. a **sequência de precedência** das treze ordens;
2. **Argissolos**: a 5ª exige B textural *imediatamente abaixo* do A ou E; a 6ª
   diz *subjacente*, nos primeiros 200 cm (regra 13);
3. **Cambissolos**: a exclusão de plintita é *load-bearing* aqui, porque na 5ª
   os Plintossolos são testados **depois** dos Cambissolos (regra 9);
4. **Neossolos**: lista de exclusões explícita na 2ª posição, em lugar da
   cláusula residual da 6ª (regra 2);
5. as **diferenças textuais menores** da própria chave, anotadas caso a caso.

⚠️ **O que foi de fato conferido no PDF da 5ª edição, em 2026-09-11**: o texto
integral da chave das treze ordens (Cap. 4, p. 111-114) e as definições de
capítulo de Argissolos (Cap. 5), Cambissolos (Cap. 6), Espodossolos (Cap. 8),
Latossolos (Cap. 10), Luvissolos (Cap. 11) e Neossolos (Cap. 12). **Não
conferidos**, e herdados de `chave6.py` por conhecimento de domínio: os
patamares do A chernozêmico, o limiar de 50% de saturação por bases, os
350 g/kg dos Nitossolos, os 300 g/kg dos Vertissolos e o critério de mudança
textural abrupta. Cada um é ponto onde o código pode divergir da norma sem que
nada acuse.

**Recorte.** As mesmas cinco ordens de `chave6.py` estão implementadas a fundo
(`no_recorte=True`): Latossolos, Argissolos, Luvissolos, Espodossolos e
Cambissolos. As outras oito entram com regra de triagem.
"""

from __future__ import annotations

from .regras import (
    Booleano, Compara, Derivado, E, Existe, Nao, Ou, Pendente, Regra, Residual,
    Seletor,
)

CHAVE = "SiBCS 5ª ed. (2018), Cap. 4, chave das ordens, p. 111-114"


def _cap(numero: int, pagina: str) -> str:
    return f"SiBCS 5ª ed. (2018), Cap. {numero}, p. {pagina}"


CHAVE_5ED: list[Regra] = [

    # 1 -----------------------------------------------------------------------
    Regra(
        classe="ORGANOSSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="hístico"), fonte=CHAVE),
            Ou(partes=(
                Compara(atributo="ESPESSURA", operador=">=", limiar=40,
                        onde=Seletor(tipo="hístico"), unidade="cm",
                        fonte=CHAVE + " — critério (b)"),
                Pendente(motivo="hístico ≥ 20 cm sobrejacente a contato lítico "
                                "ou a material com ≥ 90% (em volume) de "
                                "fragmentos > 2 mm",
                         fonte=CHAVE + " — critério (a)"),
                Pendente(motivo="hístico ≥ 60 cm com ≥ 75% (em volume) de "
                                "tecido vegetal",
                         fonte=CHAVE + " — critério (c)"),
            )),
        )),
        fonte=CHAVE, no_recorte=False,
        observacao="diferença textual para a 6ª edição: a 5ª mede os "
                   "fragmentos em **volume** e exige diâmetro **> 2 mm**; a 6ª "
                   "passou a medir em massa e a admitir ≥ 2 mm. Como o "
                   "critério está em Pendente nas duas bases, a diferença não "
                   "altera desfecho — está registrada para quem for "
                   "implementá-lo",
    ),

    # 2 -----------------------------------------------------------------------
    Regra(
        classe="NEOSSOLO",
        condicao=E(partes=(
            Derivado(predicado="sem horizonte B diagnóstico", fonte=_cap(12, "219")),
            # 🚨 21º defeito (2026-10-17), achado pelos pares da Camada de
            # Versão (`nucleo.avaliacao_versao`, D-3 da auditoria). A exclusão
            # refutava o Neossolo por qualquer glei em posição, e a norma
            # exclui só o glei "em condição diagnóstica para Gleissolos" (Cap.
            # 12, p. 219) e ressalva, no requisito (a) da Definição, "solos de
            # textura areia ou areia franca" (Cap. 3, p. 96). A condição dos
            # Gleissolos inclui a exclusão textural (Cap. 9, p. 175): um perfil
            # arenoso com glei saía sem classe nenhuma, quando a norma o leva
            # ao Neossolo (Quartzarênico hidromórfico). A ressalva dos
            # "materiais primários intemperizáveis" tem campo no contrato
            # (MATERIAIS_PRIMARIOS, por horizonte), mas a exclusão textural dos
            # Gleissolos, a que esta regra remete, não o lê; fica, como nela,
            # fora da avaliação. (Corrigido em 2026-10-17: a primeira versão
            # deste comentário dizia que o campo não existia no contrato.)
            Nao(parte=E(partes=(
                    Derivado(predicado="glei em posição diagnóstica (5ª ed.)"),
                    Derivado(predicado="sem textura areia exclusiva até 150 cm "
                                       "(5ª ed.)"),
                )),
                fonte=_cap(12, "219") + " — glei não em condição diagnóstica "
                                        "para Gleissolos; Cap. 3, p. 96, "
                                        "requisito (a), ressalva da textura "
                                        "areia ou areia franca"),
            Nao(parte=Derivado(
                    predicado="plíntico em posição que exclui o Neossolo "
                              "(5ª ed.)"),
                fonte=_cap(3, "96") + " — requisito (c); Cap. 12, p. 219"),
            Nao(parte=Derivado(
                    predicado="concrecionário ou litoplíntico em posição de "
                              "Plintossolo (5ª ed.)"),
                fonte=_cap(3, "96") + " — Conceito; Abrangência dos "
                      "Plintossolos, p. 104 (decisão 3, opção c: nunca exclui, "
                      "deixa indeterminado)"),
            Nao(parte=Existe(onde=Seletor(tipo="vértico"),
                             imediatamente_abaixo_de=("A",)),
                fonte=CHAVE + " — requisito (c)"),
            Ou(partes=(
                Nao(parte=Derivado(predicado="horizonte A chernozêmico")),
                Pendente(motivo="A chernozêmico presente, mas não conjugado "
                                "com caráter carbonático ou horizonte cálcico "
                                "— cálcico e carbonático não estão no contrato "
                                "de entrada",
                         fonte=CHAVE + " — requisito (d)"),
            ), fonte=CHAVE + " — requisito (d)"),
        )),
        fonte=_cap(12, "219"), verificada_no_capitulo=True, no_recorte=False,
        observacao="🚨 **a diferença estrutural entre as edições**. Aqui a "
                   "classe é testada em 2º lugar com lista de exclusões; na 6ª "
                   "edição é a cláusula residual da 13ª posição. Verificado em "
                   "2026-09-07 que o desfecho é o mesmo — a exclusão migrou da "
                   "prosa para a ordem. ⚠️ A exclusão de glei codificada aqui "
                   "é a do **capítulo** (geral, sem limite de profundidade), "
                   "não a da chave simplificada ('dentro de 50 cm'), que "
                   "levaria um perfil com glei a 60 cm para Neossolo quando a "
                   "API devolve Gleissolo. 🚨 O plíntico seguia a chave "
                   "('dentro de 40 cm') até 2026-10-14 — décimo defeito: "
                   "agora segue o Cap. 3 (até 150 cm sob A, E ou horizonte "
                   "pálido) e devolve I onde só o Cap. 12 exclui (150-200 cm "
                   "ou glei precedente). A disjunção do requisito (d) evita "
                   "que a regra fique indeterminada em todo perfil: só é "
                   "indeterminada quando há de fato A chernozêmico",
    ),

    # 3 -----------------------------------------------------------------------
    Regra(
        classe="VERTISSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="vértico", inicio_ate_cm=100), fonte=CHAVE),
            Compara(atributo="ARGILA", operador=">=", limiar=300,
                    onde=Seletor(principal="A", inicio_ate_cm=20),
                    unidade="g/kg", fonte=CHAVE + " — requisito (a)"),
            Pendente(motivo="fendas verticais ≥ 1 cm atingindo 50 cm no "
                            "período seco (30 cm em solos rasos)",
                     fonte=CHAVE + " — requisito (b)"),
            Pendente(motivo="ausência de contato lítico, petrocálcico ou "
                            "**duripã** nos primeiros 30 cm",
                     fonte=CHAVE + " — requisito (c)"),
            Pendente(motivo="COLE ≥ 0,06 em área irrigada ou mal drenada",
                     fonte=CHAVE + " — requisito (d)"),
        )),
        fonte=CHAVE, no_recorte=False,
        observacao="a 5ª exige ainda 'relação textural insuficiente para "
                   "identificar um B textural', que a 6ª suprimiu; e mantém o "
                   "**duripã** na lista de ausências dos 30 cm, que a 6ª "
                   "retirou. Ambos em Pendente — não alteram desfecho aqui",
    ),

    # 4 -----------------------------------------------------------------------
    Regra(
        classe="ESPODOSSOLO",
        condicao=Existe(
            onde=Seletor(tipo="B espódico"),
            imediatamente_abaixo_de=("E", "A", "H"),
            fonte=CHAVE,
        ),
        fonte=_cap(8, "165"), verificada_no_capitulo=True, no_recorte=True,
        observacao="a 5ª admite B espódico sob hístico de qualquer espessura; "
                   "a 6ª restringiu a hístico < 40 cm e acrescentou a "
                   "precedência do B espódico sobre o B textural. O limite de "
                   "200 cm (400 se A+E > 200) é idêntico nas duas edições e "
                   "não está codificado em nenhuma das duas bases. ⚠️ É aqui "
                   "que o M3 deve encontrar o maior volume de divergência: a "
                   "6ª extinguiu as três subordens da 5ª (Humilúvicos, "
                   "Ferrilúvicos, Ferri-Humilúvicos), mas isso é 2º nível — no "
                   "1º as duas bases concordam",
    ),

    # 5 -----------------------------------------------------------------------
    Regra(
        classe="PLANOSSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="B textural"),
                   imediatamente_abaixo_de=("A", "E"), fonte=CHAVE),
            Derivado(predicado="mudança textural abrupta",
                     fonte=_cap(15, "251")),
            Nao(parte=Existe(onde=Seletor(tipo="plíntico")),
                fonte=CHAVE + " — B plânico não coincidente com o plíntico"),
            Pendente(motivo="estrutura prismática/colunar ou em blocos com "
                            "permeabilidade lenta, que define o B plânico",
                     fonte=_cap(15, "251")),
        )),
        fonte=CHAVE, no_recorte=False,
        observacao="a 5ª exige apenas a não coincidência com o horizonte "
                   "plíntico (sem caráter sódico); a 6ª estendeu a exigência "
                   "ao horizonte **concrecionário**. Triagem: sem o critério "
                   "estrutural, um Planossolo real sai como indeterminado — "
                   "nunca como outra ordem",
    ),

    # 6 -----------------------------------------------------------------------
    Regra(
        classe="GLEISSOLO",
        condicao=E(partes=(
            Derivado(predicado="glei em posição diagnóstica (5ª ed.)", fonte=_cap(9, "175")),
            Nao(parte=Existe(onde=Seletor(tipo="B diagnóstico")),
                fonte=_cap(9, "175")),
            Derivado(predicado="sem textura areia exclusiva até 150 cm (5ª ed.)",
                     fonte=_cap(9, "175")),
            Nao(parte=Existe(onde=Seletor(tipo="plíntico", inicio_ate_cm=200)),
                fonte=CHAVE + " — sem plíntico, concrecionário ou "
                              "litoplíntico dentro de 200 cm"),
        )),
        fonte=_cap(9, "175"), verificada_no_capitulo=True, no_recorte=False,
        observacao="🚨 diferença *load-bearing* de precedência: na 5ª os "
                   "Plintossolos vêm **depois** (10ª), então a exclusão de "
                   "plíntico dentro de 200 cm precisa ser escrita — a 5ª a "
                   "enuncia como proibição incondicional. A 6ª trocou por "
                   "condicional ('não satisfazem aos requisitos para "
                   "Planossolos e Plintossolos') justamente porque moveu "
                   "Plintossolos para a 5ª posição. Mesmo desfecho, forma "
                   "diferente — ver [[diff-sibcs-5ed-6ed-classolosbr]] §1. "
                   "Mantém-se a simplificação declarada de chave6.py: a norma "
                   "proíbe B diagnóstico *acima* do glei, aqui proíbe-se em "
                   "todo o perfil",
    ),

    # 7 -----------------------------------------------------------------------
    Regra(
        classe="LATOSSOLO",
        condicao=Existe(
            onde=Seletor(tipo="B latossólico"),
            imediatamente_abaixo_de=("A",),
            fonte=CHAVE,
        ),
        fonte=_cap(10, "195"), verificada_no_capitulo=True, no_recorte=True,
        observacao="as duas edições dizem o mesmo, palavra por palavra: "
                   "'B latossólico precedido de qualquer tipo de horizonte A' "
                   "nos primeiros 200 cm, ou 300 cm se o A tiver mais de "
                   "150 cm. ⚠️ 'Precedido' não é 'imediatamente abaixo', e "
                   "ambas as bases codificam adjacência — a leitura estrita "
                   "vem da chave, não do capítulo. Divergência de modelagem "
                   "herdada, idêntica nos dois lados, portanto invisível ao M3",
    ),

    # 8 -----------------------------------------------------------------------
    Regra(
        classe="CHERNOSSOLO",
        condicao=E(partes=(
            Derivado(predicado="horizonte A chernozêmico", fonte=_cap(7, "157")),
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
        observacao="texto praticamente idêntico ao da 6ª edição; a 5ª "
                   "acrescenta a variante 'Bi com espessura inferior a 10 cm "
                   "ou horizonte C, ambos cálcicos', que cai no mesmo Pendente",
    ),

    # 9 -----------------------------------------------------------------------
    Regra(
        classe="CAMBISSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="B incipiente"),
                   imediatamente_abaixo_de=("A", "H"), fonte=CHAVE),
            Nao(parte=Existe(onde=Seletor(tipo="plíntico", inicio_ate_cm=40)),
                fonte=_cap(6, "139") + " — plintita e petroplintita, se "
                                       "presentes, não satisfazem aos "
                                       "requisitos para Plintossolos"),
        )),
        fonte=_cap(6, "139"), verificada_no_capitulo=True, no_recorte=True,
        observacao="🚨 **a exclusão de plintita é load-bearing nesta edição**, "
                   "e é a razão de ela existir na prosa da 5ª: Plintossolos "
                   "são testados na 10ª posição, depois dos Cambissolos. Na 6ª "
                   "edição Plintossolos subiram para a 5ª posição e a frase "
                   "sumiu do capítulo — a ordem passou a fazer o trabalho. As "
                   "demais exclusões do mesmo período (glei, vértico) são "
                   "redundantes já na 5ª, porque Gleissolos (6ª) e Vertissolos "
                   "(3ª) vêm antes; não foram codificadas, para não introduzir "
                   "assimetria de modelagem frente a chave6.py. ⚠️ A 5ª "
                   "admite o A chernozêmico como horizonte superficial quando "
                   "o Bi tem Ta e V alta; a 6ª o move para dentro do parêntese "
                   "de exceção. Nas duas edições Chernossolos são testados "
                   "antes, então o caso não chega aqui",
    ),

    # 10 ----------------------------------------------------------------------
    Regra(
        classe="PLINTOSSOLO",
        condicao=Ou(partes=(
            Existe(onde=Seletor(tipo="plíntico", inicio_ate_cm=40), fonte=CHAVE),
            Existe(onde=Seletor(tipo="concrecionário", inicio_ate_cm=40),
                   fonte=CHAVE),
            Existe(onde=Seletor(tipo="litoplíntico", inicio_ate_cm=40),
                   fonte=CHAVE),
            Derivado(predicado="plíntico até 200 cm em posição diagnóstica (5ª ed.)",
                     fonte=CHAVE + " — condição (b)"),
        )),
        fonte=CHAVE, no_recorte=False,
        observacao="mesma formulação da 6ª edição; muda a posição, de 10ª "
                   "para 5ª. A 5ª exige ainda que o plíntico não seja "
                   "coincidente com B plânico de caráter sódico — não "
                   "codificado, como na 6ª",
    ),

    # 11 ----------------------------------------------------------------------
    Regra(
        classe="LUVISSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="B textural"),
                   imediatamente_abaixo_de=("A", "E"), fonte=CHAVE),
            Compara(atributo="ATIVIDADE_ARGILA", operador=">=", limiar=27,
                    onde=Seletor(tipo="B textural", seccao_controle_cm=100),
                    agregacao="maior parte",
                    unidade="cmolc/kg de argila",
                    fonte=_cap(11, "213") + " — argila de atividade alta na "
                                            "maior parte dos primeiros 100 cm "
                                            "do B (inclusive BA)"),
            Compara(atributo="V_PERCENT", operador=">=", limiar=50,
                    onde=Seletor(tipo="B textural", seccao_controle_cm=100),
                    agregacao="maior parte", unidade="%",
                    fonte=_cap(11, "213") + " — saturação por bases alta"),
        )),
        fonte=_cap(11, "213"), verificada_no_capitulo=True, no_recorte=True,
        observacao="a 5ª diz 'imediatamente abaixo de qualquer tipo de A "
                   "(exceto A chernozêmico) ou sob horizonte E'; a 6ª diz "
                   "'subjacente', nos primeiros 200 cm, e detalha a seção de "
                   "controle como 'inclusive BA ou BE e exclusive BC'. ⚠️ "
                   "chave6.py codifica adjacência para os Luvissolos e "
                   "profundidade para os Argissolos, embora a 6ª use a mesma "
                   "palavra nos dois capítulos — inconsistência herdada, "
                   "reproduzida aqui para manter a comparabilidade. O 'exceto "
                   "A chernozêmico' não é codificado em nenhuma das duas "
                   "bases: Chernossolos são testados antes nas duas edições. "
                   "O empate exato da agregação 'maior parte' devolve "
                   "indeterminado — é o caso `GeoTab_RN_007_Acu`",
    ),

    # 12 ----------------------------------------------------------------------
    Regra(
        classe="NITOSSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="B nítico"), fonte=CHAVE),
            Compara(atributo="ARGILA", operador=">=", limiar=350,
                    onde=Seletor(principal="A"), unidade="g/kg",
                    fonte=CHAVE + " — argila inclusive no A"),
            Pendente(motivo="argila de atividade baixa, ou alta desde que "
                            "conjugada com caráter alumínico, na maior parte "
                            "dos primeiros 100 cm do B",
                     fonte=CHAVE),
        )),
        fonte=CHAVE, no_recorte=False,
        observacao="a 5ª exige 'B nítico abaixo do horizonte A' e condiciona a "
                   "atividade da argila na chave; a 6ª remete a policromia ao "
                   "capítulo. Os dois casos caem em Pendente",
    ),

    # 13 ----------------------------------------------------------------------
    Regra(
        classe="ARGISSOLO",
        condicao=E(partes=(
            Existe(onde=Seletor(tipo="B textural"),
                   imediatamente_abaixo_de=("A", "E"),
                   fonte=_cap(5, "115")),
            Derivado(predicado="requisitos (a) e (b) da Definição dos "
                               "Argissolos (5ª ed.)",
                     fonte=_cap(3, "87") + " — plíntico e glei não acima "
                                           "nem coincidentes com o topo do Bt"),
            Residual(fonte=CHAVE),
        )),
        fonte=_cap(5, "115"), verificada_no_capitulo=True, no_recorte=True,
        observacao="A 5ª exige 'B textural **imediatamente abaixo** do A ou "
                   "E' no Cap. 5 e na Definição do Cap. 3 — sem ambiguidade. "
                   "Um perfil com Bi logo abaixo do A e Bt fundo é CAMBISSOLO "
                   "por esta base, como devolve a API. Na 6ª (chave6.py) o "
                   "mesmo perfil fica **indeterminado** entre Argissolo e "
                   "Cambissolo, porque a 6ª é internamente inconsistente "
                   "sobre a posição do Bt (2026-10-15; antes desta data esta "
                   "observação dizia, sem razão, que a 6ª o fazia ARGISSOLO). "
                   "🚨 Requisitos (a) e (b) da Definição acrescentados em "
                   "2026-10-15 — décimo segundo defeito. Os critérios de "
                   "atividade da argila não são codificados: discriminam "
                   "dentro da ordem, e a precedência dos Luvissolos os cobre",
    ),
]


def cobertura() -> str:
    """Relatório do que está implementado, para não confundir escopo com fé."""
    linhas = ["| # | Classe | Recorte | Capítulo conferido | Pendências |",
              "|---|---|---|---|---|"]
    for i, regra in enumerate(CHAVE_5ED, 1):
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
