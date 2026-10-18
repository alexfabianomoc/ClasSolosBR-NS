"""Identificação dos horizontes diagnósticos.

Este módulo é a resposta a um achado empírico sobre o sistema de referência
(2026-09-07, ver `[[simbolo-de-horizonte-como-entrada-diagnostica]]`): o
SmartSolos **não deduz** o horizonte diagnóstico dos atributos analíticos — ele
o lê do símbolo. Suprimido o sufixo, com todos os valores preservados, perfis
de seis ordens distintas passam a ser classificados como Neossolos; trocado o
sufixo, o perfil assume a classe que o novo símbolo nomeia. O dado pode
**vetar** a alegação do símbolo, mas não a substitui.

A implementação aqui adota a mesma leitura, e a torna explícita:

    o símbolo **propõe** o tipo diagnóstico;
    o dado, quando existe, **confirma ou veta**;
    nada é proposto pelo dado sozinho.

A última linha é deliberada e é uma limitação declarada, não um esquecimento:
inferir o tipo diagnóstico a partir dos atributos é tarefa do componente 4.2.5
(Inferidor de Horizonte Diagnóstico), que é orientado a dados e fica fora do
núcleo simbólico. Misturar as duas coisas destruiria o invariante de §4.1.

Cada identificação carrega a `origem`, que atravessa a árvore de prova até a
saída — para que nenhuma classificação apoiada em símbolo inferido se
apresente indistinguível de uma apoiada em símbolo observado.

Fonte do vocabulário de sufixos: `sentinela.gramatica_sufixos`, que o
formaliza a partir de LARACH et al. (1988) e LEMOS; SANTOS (1996). O SiBCS
**usa** esse vocabulário e não o define — é preciso ir aos manuais.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# `sentinela` vive em `dags/`, ao lado dos fluxos. O núcleo o consome sem
# depender do Airflow.
_DAGS = Path(__file__).resolve().parent.parent / "dags"
if str(_DAGS) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(_DAGS))

from sentinela import gramatica_sufixos as gs  # noqa: E402

from .logica import F, I, V  # noqa: E402
from .perfil import INDETERMINADA, Horizonte, Perfil  # noqa: E402


def leitura_atual(simbolo: str) -> str | None:
    """Símbolo em notação atual, ou None quando não há leitura a usar.

    `gs.moderniza` só traduz a notação anterior quando a tradução é única.
    🚨 Decisão do usuário de 2026-10-16, opção (b): quando o símbolo antigo
    tem **mais de uma** tradução (Larach et al., 1988, Anexo 1: `B1` → `BA`
    ou `BE`), mas todas concordam na letra do horizonte principal e nos
    sufixos — `B1t` → `BAt` ou `BEt` —, a ambiguidade está só na letra que
    diz o que fica acima do B, e ela não muda o tipo do horizonte. Usa-se a
    primeira leitura. Quando as traduções discordam (`A3g` → `ABg` ou
    `EBg`), devolve None, e `_identificar_horizonte` deixa **pendentes** os
    tipos que as leituras propõem.

    ⚠️ Leitura declarada: com a primeira tradução, o `B1t` passa por `BAt`,
    e não por `BEt`, nos poucos predicados de subgrupo que distinguem o BA
    (`predicados_subgrupos`). Medido em 2026-10-16 antes de aplicar: 638
    horizontes do BDSolos com leituras concordantes, 53 discordantes.
    """
    moderno = gs.moderniza(simbolo)
    if moderno:
        return moderno
    if _leituras_concordam(simbolo):
        return gs.leituras(simbolo)[0]
    return None


def _leituras_concordam(simbolo: str) -> bool:
    """Mais de uma tradução, todas com a mesma letra principal e os mesmos sufixos."""
    leituras = gs.leituras(simbolo)
    if len(leituras) < 2:
        return False
    analises = [gs.analisa(x) for x in leituras]
    return (len({(a.principal or "")[:1] for a in analises}) == 1
            and len({tuple(a.sufixos) for a in analises}) == 1)


def leituras_atuais(simbolo: str) -> list[str]:
    """Todas as leituras do símbolo em notação atual.

    A tradução única quando existe; as várias traduções de um símbolo antigo
    ambíguo; o próprio símbolo nos demais casos. Serve às perguntas em que
    basta que **todas** as leituras concordem — se o horizonte é transicional,
    se a letra principal está num conjunto —, e não exige escolher uma.
    """
    moderno = gs.moderniza(simbolo)
    if moderno:
        return [moderno]
    return gs.leituras(simbolo) or [simbolo]


def principais_possiveis(h: Horizonte) -> set[str]:
    """Letras de horizonte principal que as leituras do símbolo admitem.

    `A3` (`AB` ou `EB`) admite {"A", "E"}: a verificação "imediatamente abaixo
    do A ou E" passa, porque todas as leituras a satisfazem (opção b).
    """
    return {(gs.analisa(x).principal or "")[:1] for x in leituras_atuais(h.simbolo)}


def _leituras_discordam(simbolo: str) -> bool:
    """Símbolo antigo com mais de uma tradução que discordam entre si."""
    return (gs.moderniza(simbolo) is None and len(gs.leituras(simbolo)) > 1
            and not _leituras_concordam(simbolo))


#: Sufixo → tipo de horizonte diagnóstico que ele **propõe**.
#: Apenas os sufixos cuja leitura foi confirmada experimentalmente no sistema
#: de referência entram aqui. Os demais são anotação descritiva.
PROPOSTO_POR_SUFIXO: dict[str, str] = {
    "t": "B textural",
    "w": "B latossólico",
    "i": "B incipiente",
    "g": "glei",
    "h": "B espódico",
    "s": "B espódico",
    "f": "plíntico",
    "c": "concrecionário",
    "v": "vértico",
}

#: Combinações que designam tipo distinto do que cada letra isolada designa.
#: `o`+`d` em horizonte hístico é o exemplo canônico: isoladas, as letras
#: designam os graus extremos de decomposição; juntas, o intermediário.
COMPOSTOS: dict[tuple[str, ...], str] = {
    ("c", "m"): "litoplíntico",
}

#: Horizontes principais que caracterizam material orgânico.
PRINCIPAIS_ORGANICOS = frozenset({"H", "O"})

#: Letras de horizonte principal da norma de notação (Larach et al., 1988).
#: Usadas para separar o transicional (`BA`, `BC`) do B com sufixo ilegível.
LETRAS_PRINCIPAIS = frozenset("HOAEBCFR")

#: Tipos de B diagnóstico que um B sem sufixo legível pode ser. O símbolo não
#: propõe nenhum deles nem exclui nenhum.
TIPOS_B_POR_SIMBOLO = ("B textural", "B latossólico", "B incipiente",
                       "B espódico", "B nítico")


@dataclass(frozen=True)
class Identificacao:
    """Um tipo diagnóstico atribuído a um horizonte, com sua procedência."""

    horizonte: Horizonte
    tipo: str
    origem: str          # "símbolo" | "símbolo (vetado pelo dado)" |
                         # "símbolo (veto pendente)" | "dado"
    observacao: str = ""

    @property
    def valida(self) -> bool:
        """Identificação afirmada: não vetada e sem veto pendente."""
        return "vetado" not in self.origem and "pendente" not in self.origem

    @property
    def indeterminada(self) -> bool:
        """O símbolo propõe, e falta o dado que poderia vetar.

        🚨 Décimo primeiro defeito (2026-10-14). Antes, a falta do dado que
        poderia vetar deixava a identificação **aceita**: um `Btf` sem cor
        nenhuma concluía PLINTOSSOLO, e medir a cor (avermelhada, sem
        mosqueado) mudava a classe para uma que não estava no conjunto
        alcançável — a garantia de contenção da seção 4.2.4 da monografia
        não valia. "Ausência de dado nunca veta" estava certo; faltava o
        simétrico: ausência de dado também não afirma.
        """
        return "pendente" in self.origem


def principal(h: Horizonte) -> str:
    """Letra do horizonte principal, ignorando o dígito de descontinuidade.

    ⚠️ `2Btn`, `3Cg`, `11C1g` começam com dígito. Fatiar o símbolo com
    `[:1]` devolve `"2"` e o horizonte deixa de ser reconhecido como B —
    defeito que apagou a mudança textural abrupta de quatro Planossolos
    (`PE_041`, `PE_046`, `RN_025`, `RN_040`) em 2026-09-07. Use sempre esta
    função, nunca o fatiamento.
    """
    moderno = leitura_atual(h.simbolo)
    s = gs.analisa(moderno if moderno else h.simbolo)
    return (s.principal or "")[:1]


def identificar(perfil: Perfil) -> list[Identificacao]:
    """Devolve as identificações de todos os horizontes do perfil."""
    achados: list[Identificacao] = []
    for h in perfil.horizontes:
        achados.extend(_identificar_horizonte(perfil, h))
    return achados


def tipos_de(perfil: Perfil, horizonte: Horizonte) -> set[str]:
    """Tipos diagnósticos válidos de um horizonte."""
    return {
        i.tipo for i in _identificar_horizonte(perfil, horizonte) if i.valida
    }


def horizontes_do_tipo(perfil: Perfil, tipo: str) -> list[Horizonte]:
    """Horizontes cuja identificação válida inclui `tipo`, do topo à base."""
    return [
        i.horizonte for i in identificar(perfil)
        if i.tipo == tipo and i.valida
    ]


def horizontes_indeterminados_do_tipo(perfil: Perfil, tipo: str) -> list[Horizonte]:
    """Horizontes que o símbolo propõe como `tipo` com veto pendente."""
    return [
        i.horizonte for i in identificar(perfil)
        if i.tipo == tipo and i.indeterminada
    ]


def tem_b_diagnostico(perfil: Perfil) -> bool:
    """Se há algum horizonte B diagnóstico — o gate dos Neossolos."""
    tipos_b = {"B textural", "B latossólico", "B incipiente",
               "B espódico", "B nítico", "B plânico"}
    return any(
        i.tipo in tipos_b and i.valida for i in identificar(perfil)
    )


def b_sem_sufixo_legivel(simbolo) -> bool:
    """O símbolo é um B que não diz de que tipo é?

    Verdadeiro para `B`, `B1`, `B21`, `2B`, `IIB2` (modernizado para `2B2`
    por `_identificar_horizonte` antes da chamada) e `BW`;
    falso para os transicionais (`BA`, `BC`, cujo resto é letra principal),
    para os mesclados (`B/A`) e para qualquer B com sufixo minúsculo (`Bt`,
    `Bcn`). ⚠️ `Bcn`, `Bn` — B com sufixo que não designa tipo — continuam
    fora: a decisão de 2026-10-15 alcança só o B sem sufixo nenhum.
    """
    p = simbolo.principal or ""
    if simbolo.mesclado or not p.startswith("B"):
        return False
    if any(c in LETRAS_PRINCIPAIS for c in p[1:]):
        return False
    return not simbolo.sufixos


def b_indeterminados(perfil: Perfil) -> list[Horizonte]:
    """Horizontes com algum tipo de B diagnóstico pendente."""
    vistos, saida = set(), []
    for i in identificar(perfil):
        if i.indeterminada and i.tipo.startswith("B ") and id(i.horizonte) not in vistos:
            vistos.add(id(i.horizonte))
            saida.append(i.horizonte)
    return saida


# ------------------------------------------------------------- internos -----

def _identificar_horizonte(perfil: Perfil, h: Horizonte) -> list[Identificacao]:
    if _leituras_discordam(h.simbolo):
        # Opção (b), 2026-10-16: traduções que discordam (`A3g` → `ABg` ou
        # `EBg`). Cada tipo que alguma leitura propõe fica **pendente** — o
        # símbolo não permite afirmá-lo, e a falta de leitura não o refuta.
        vistos, saida = set(), []
        for leitura in gs.leituras(h.simbolo):
            outro = Horizonte(leitura, h.limite_sup, h.limite_inf, h.atributos)
            for i in _identificar_horizonte(perfil, outro):
                if i.tipo in vistos:
                    continue
                vistos.add(i.tipo)
                saida.append(Identificacao(
                    h, i.tipo, "símbolo antigo com leituras discordantes "
                    "(identificação pendente)",
                    f"{h.simbolo}: " + " ou ".join(gs.leituras(h.simbolo))))
        return saida
    simbolo = gs.analisa(h.simbolo)
    origem_extra = ""
    # Notação anterior a 1988 (`11C1g`, `IIBt`, `(B)`). O sentinela sabe
    # traduzir; sem isso, o horizonte fica sem tipo e a classe cai no
    # resíduo — foi o que aconteceu com `GeoTab_RN_021_Ceara_Mirim`.
    # 🚨 Décimo quarto defeito (2026-10-15): a tradução só era tentada quando
    # `gs.analisa` **não** reconhecia o símbolo, e ela reconhece `IIBt1`
    # lendo "II" como horizonte principal. O B textural de perfis em notação
    # com algarismo romano não era identificado. `moderniza` devolve None
    # para notação vigente e só traduz quando a norma é unívoca, então é
    # tentada primeiro. Achado na transcrição das fichas originais
    # (`PE_013`, `PE_040`, `PE_041`). ⚠️ `gramatica_sufixos.analisa` não foi
    # alterada: os números do Quadro 5 da monografia saem dela.
    moderno = leitura_atual(h.simbolo)
    if moderno:
        simbolo = gs.analisa(moderno)
        origem_extra = f" via notação modernizada ({h.simbolo} → {moderno})"
    achados: list[Identificacao] = []

    if simbolo.mesclado:
        # `B/E`, `2Bt/Bw`: o horizonte é transicional mesclado. A norma trata
        # cada componente; aqui sinaliza-se e não se propõe tipo, para não
        # afirmar o que a norma resolve caso a caso.
        return [Identificacao(h, "mesclado", "símbolo",
                              "horizonte mesclado — tipo não proposto")]

    if b_sem_sufixo_legivel(simbolo):
        # Decisão de 2026-10-15 (opção 1 do usuário). Na notação anterior a
        # 1988 o B se numera (`B1`, `B21`, `B22`) e não leva o sufixo que
        # designa o tipo; em `BW` a letra está em maiúscula, e lê-la como `w`
        # seria a uniformização de caixa que a §3.5 veda. O símbolo não diz
        # que B é — e ausência de informação não refuta (§4.2.1), nem afirma
        # (11º defeito). Cada tipo de B diagnóstico fica **pendente**: a
        # condição que o pede fica indeterminada, e a classe, alcançável.
        # Antes, nenhum tipo era proposto e o B era lido como inexistente:
        # 1.380 Latossolos do BDSolos eram refutados assim.
        # ⚠️ Mitigação 5: o problema foi achado no BDSolos; a justificativa é
        # a norma de notação e a semântica de três valores, não o rótulo.
        return [Identificacao(
            h, tipo, "símbolo sem sufixo diagnóstico (identificação pendente)"
            + origem_extra,
            f"{h.simbolo}: B sem sufixo que designe o tipo")
            for tipo in TIPOS_B_POR_SIMBOLO]

    if simbolo.principal and simbolo.principal[0] in PRINCIPAIS_ORGANICOS:
        achados.append(Identificacao(h, "hístico", "símbolo"))

    sufixos = tuple(s.rstrip(gs.MACRON) for s in simbolo.sufixos)

    for combinacao, tipo in COMPOSTOS.items():
        if all(c in sufixos for c in combinacao):
            achados.append(Identificacao(h, tipo, "símbolo"))

    for s in sufixos:
        tipo = PROPOSTO_POR_SUFIXO.get(s)
        if not tipo:
            continue
        # O `t`/`w`/`i` só designam horizonte B quando o principal é B.
        if tipo.startswith("B ") and not simbolo.principal.startswith("B"):
            continue
        veto = _veto(perfil, h, tipo)
        pendente = None if veto else _veto_pendente(perfil, h, tipo)
        if veto:
            origem = "símbolo (vetado pelo dado)"
        elif pendente:
            origem = "símbolo (veto pendente)"
        else:
            origem = "símbolo"
        achados.append(
            Identificacao(h, tipo, origem + origem_extra, veto or pendente or "")
        )

    achados.extend(_nitico(perfil, h, sufixos, simbolo))
    return achados


#: Limite da relação textural B/A do horizonte **B nítico**.
#: SiBCS 6ª ed., Cap. 2: "sem incremento de argila do horizonte superficial
#: para o subsuperficial ou com pequeno incremento, traduzido em relação
#: textural B/A sempre menor ou igual a 1,5". Idêntico na 5ª edição.
#: ⚠️ Este limite é do B nítico, **não** do B latossólico — a confusão entre
#: os dois custou três Latossolos refutados indevidamente (ver `_veto`).
RT_MAXIMA_NITICO = 1.5

#: Limiares da relação textural que caracterizam um B textural — **existem
#: apenas na 5ª edição** (2018, Cap. 2): relação > 1,50 se o A tem mais de
#: 400 g/kg de argila; > 1,70 entre 150 e 400; > 1,80 abaixo de 150.
#: A 6ª edição **suprimiu os números** e passou a definir o B textural de
#: forma qualitativa ("o teor de argila do horizonte B textural é maior que o
#: do horizonte A ou E"), com a cerosidade como critério de campo.
#: Mantidos aqui por serem insumo da Camada de Versão, e **não usados** pelo
#: núcleo da 6ª edição.
RT_B_TEXTURAL_5ED = ((400, 1.50), (150, 1.70), (0, 1.80))


#: Espessura mínima do horizonte plíntico. SiBCS 5ª ed., Cap. 2, p. 67:
#: "presença de plintita em quantidade igual ou superior a 15% (por volume) e
#: espessura de pelo menos 15 cm". Idêntico na 6ª edição.
#: ⚠️ A **quantidade** (15% por volume) não existe em nenhum dos 57 campos do
#: contrato nem nos 62 do acervo curado — é inverificável, e por isso não
#: sustenta veto. A espessura, sim: sai de `LIMITE_SUP`/`LIMITE_INF`.
ESPESSURA_MINIMA_PLINTICO = 15.0

#: Espessura mínima do horizonte B latossólico. SiBCS 5ª ed., Cap. 2, p. 57:
#: "O horizonte B latossólico deve apresentar espessura mínima de 50 cm".
#: ⚠️ A norma não diz se os transicionais BA e BC entram na conta. Ver
#: `_espessura_b_latossolico`.
ESPESSURA_MINIMA_B_LATOSSOLICO = 50.0

#: Matizes que a norma admite como **cor clara** do horizonte plíntico, com o
#: croma máximo de cada um. SiBCS 5ª ed., Cap. 2, p. 67: "a) Matizes de 2,5Y a
#: 5Y; ou b) Matizes de 10YR a 7,5YR, com cromas baixos, usualmente até 4,
#: podendo atingir 6 quando se tratar de matiz 10YR".
CROMA_MAXIMO_COR_CLARA = {"2.5Y": None, "5Y": None, "10YR": 6.0, "7.5YR": 4.0}


#: Matizes que a condição (b) dos Plintossolos admite no horizonte
#: **precedente** do plíntico, com o croma máximo de cada um — e a diferença
#: entre as edições, que é real e foi conferida nos dois PDFs em 2026-09-17.
#:
#: 5ª ed. (Cap. 16, p. 261): "a) Matiz 5Y; ou b) Matizes 7,5YR, 10YR ou 2,5Y
#: com croma menor ou igual a 4".
#: 6ª ed. (Cap. 16, p. 270): "a) Matiz 5Y **ou matizes mais acinzentados,
#: esverdeados ou azulados**; ou b) Matizes 7,5YR, 10YR ou 2,5Y, **com valor
#: maior ou igual a 5** e com croma menor ou igual a 4".
#:
#: ⚠️ Não confundir com `CROMA_MAXIMO_COR_CLARA`, que é a especificação das
#: cores claras **do próprio** horizonte plíntico e admite croma 6 em 10YR.
#: São duas listas parecidas e distintas, na mesma norma.
CROMA_MAXIMO_PALIDA_PRECEDENTE = {"7.5YR": 4.0, "10YR": 4.0, "2.5Y": 4.0}

#: Passos válidos dentro de uma família de matiz na carta de Munsell.
PASSOS_DE_MATIZ = frozenset({2.5, 5.0, 7.5, 10.0})

#: Famílias de matiz iguais ou mais acinzentadas, esverdeadas ou azuladas que
#: 5Y, para o item (a) da 6ª edição.
FAMILIAS_ACINZENTADAS = frozenset({"GY", "G", "BG", "B", "PB"})


def _matiz(valor) -> tuple[float | None, str] | None:
    """Parte numérica e família de um matiz Munsell (`10YR` → `(10.0, "YR")`).

    Devolve `None` quando o texto não é um matiz reconhecível. O acervo curado
    traz `10 YR`, `2.5 Y`, `19YR`, `5Y4` e `7.Y` — espaço interno, vírgula e
    erro de digitação —, de modo que normalizar é obrigatório e **não
    reconhecer é `None`, nunca "matiz avermelhado"**: um erro de digitação não
    pode virar refutação silenciosa.
    """
    if valor is None:
        return None
    texto = str(valor).upper().replace(",", ".")
    texto = "".join(c for c in texto if not c.isspace())
    if texto == "N":
        return (None, "N")    # neutro (cinza), sem matiz numérico
    for familia in ("RP", "PB", "YR", "GY", "BG", "R", "Y", "G", "B", "P"):
        if texto.endswith(familia):
            numero = texto[: -len(familia)]
            try:
                passo = float(numero)
            except ValueError:
                return None
            # A carta de Munsell tem quatro passos por família. `19YR` e `7.Y`
            # existem no acervo e não são matizes: devolver `None` os manda
            # para a indeterminação, e é o sentinela que deve reclamar deles.
            return (passo, familia) if passo in PASSOS_DE_MATIZ else None
    return None


def _cor_clara(matiz, croma) -> bool | None:
    """A cor é das que a norma admite como cor clara do plíntico?

    Devolve `None` quando falta matiz ou croma, ou quando o matiz não é
    reconhecível — ausência de dado não decide.
    """
    if croma is None:
        return None
    analisado = _matiz(matiz)
    if analisado is None:
        return None
    numero, familia = analisado
    if familia == "N":
        return True           # neutro é cinza, a cor clara por excelência
    m = f"{numero:g}{familia}"
    if m not in CROMA_MAXIMO_COR_CLARA:
        return False          # matiz mais avermelhado que 7,5YR
    limite = CROMA_MAXIMO_COR_CLARA[m]
    return limite is None or float(croma) <= limite


def _cor_palida_precedente(matiz, valor, croma, edicao: str) -> bool | None:
    """A cor satisfaz os itens (a) ou (b) da condição (b) dos Plintossolos?

    Devolve `None` quando o dado não decide. ⚠️ O matiz `N` (neutro) entra
    como pálido nas duas edições: a 6ª o alcança por "matizes mais
    acinzentados", e na 5ª a inclusão é **interpretação declarada** — o item
    (a) lista "Matiz 5Y", e o texto que ele qualifica fala de "coloração
    pálida (acinzentada ou amarelado clara)", que é o que o neutro nomeia.
    """
    analisado = _matiz(matiz)
    if analisado is None:
        return None
    numero, familia = analisado

    # item (a)
    if familia == "N":
        return True
    if familia in FAMILIAS_ACINZENTADAS:
        return True if edicao == "6" else False
    if familia == "Y" and numero is not None:
        if numero == 5:
            return True
        if numero > 5:
            return True if edicao == "6" else False

    # item (b)
    m = f"{numero:g}{familia}" if numero is not None else familia
    if m not in CROMA_MAXIMO_PALIDA_PRECEDENTE:
        return False
    if croma is None:
        return None
    if float(croma) > CROMA_MAXIMO_PALIDA_PRECEDENTE[m]:
        return False
    if edicao == "6":
        if valor is None:
            return None
        return float(valor) >= 5
    return True


def _veto(perfil: Perfil, h: Horizonte, tipo: str) -> str | None:
    """O dado refuta o que o símbolo propõe? Devolve o motivo, ou None.

    Só se veta com dado presente, e só quando a refutação é inequívoca pela
    norma. Ausência de dado nunca veta — seria transformar silêncio em
    refutação, e é o que a lógica de três valores existe para evitar.

    🚨 **Há veto para o plíntico, e ele nasceu de um erro medido**
    (`GeoTab_RN_043_Pedro_Avelino`, 2026-09-17). O sufixo `f` denota, pela
    norma de notação (LARACH et al., 1988, p. 43), "material laterítico e/ou
    bauxítico brando (plintita)" — a **presença do material**. O horizonte
    plíntico é outra coisa: exige 15% de plintita por volume, 15 cm de
    espessura e um arranjo de cores vermelhas com acinzentadas ou brancas. Ler
    o sufixo como o horizonte fazia o núcleo afirmar PLINTOSSOLO num perfil
    que os curadores reclassificaram **de** Plintossolo **para** Luvissolo,
    mantendo o `f` justamente porque plintita existe e horizonte plíntico não.
    São dois vetos, e nenhum deles inventa número:

    1. **espessura < 15 cm**, com os dois limites presentes — refutação direta
       do texto da norma;
    2. **matriz registrada que a norma não admite como cor clara, sem nenhum
       mosqueado claro registrado**. Sem cor clara no horizonte, o arranjo
       "vermelhas e acinzentadas ou brancas" não se sustenta. ⚠️ O veto exige
       a **matriz presente**: quando ela falta e só há mosqueados — convenção
       de registro de `PE_048` e `RN_044`, ambos Plintossolos legítimos —, não
       há refutação. E matriz clara **sem** mosqueado registrado (caso de
       `RN_042`) também não veta: aí o que falta é o registro do mosqueado,
       não a cor clara.

    🚨 **Há veto de espessura para o B latossólico** desde o 20º defeito
    (2026-10-17): ver `_espessura_b_latossolico`. O parágrafo seguinte trata
    só da relação textural.

    ⚠️ **Não há veto de relação textural para o B latossólico.** Duas
    tentativas foram feitas e
    ambas estavam erradas, por motivos diferentes:

    1. limiares variáveis 1,80 / 1,70 / 1,50 conforme a argila do A — números
       corretos, mas da **5ª edição**, que a 6ª suprimiu;
    2. limite fixo de 1,5 — número correto, mas do **B nítico**, atribuído por
       engano ao B latossólico.

    O que a 6ª edição de fato diz sobre o B latossólico é **relativo**, não
    numérico: o incremento de argila deve apresentar "valores menores que
    aqueles necessários para caracterizar um horizonte B textural" — e a 6ª
    não numera esses valores. Sem número na norma, não há veto defensável, e
    inventar um refuta Latossolos legítimos em silêncio. Fica declarado como
    limitação, não como pendência a preencher com um palpite.
    """
    if tipo == "B latossólico":
        return _espessura_b_latossolico(perfil, h)[0]
    if tipo != "plíntico":
        return None

    espessura = h.espessura
    if espessura is not None and espessura < ESPESSURA_MINIMA_PLINTICO:
        return (f"espessura de {espessura:g} cm, abaixo dos "
                f"{ESPESSURA_MINIMA_PLINTICO:g} cm mínimos do horizonte plíntico")

    # 🚨 Décimo oitavo defeito (2026-10-17), achado pela ablação do Avaliador
    # Parcial no acervo nacional (`BDSolos|600|5823|TS 5`, sem o croma do
    # mosqueado do Bgf2: PLINTOSSOLO fora do conjunto alcançável). O veto
    # refutava quando nenhum mosqueado era *comprovadamente* claro, e um
    # mosqueado registrado com a cor incompleta contava como "não claro".
    # Agora só o mosqueado **não registrado** é ausência observada; o
    # registrado com cor incompleta não veta e deixa a identificação pendente
    # (`_veto_pendente`). Mesma natureza do 13º: falta de dado não refuta.
    matriz = _cor_clara(h.get("COR_UMIDA_MATIZ"), h.get("COR_UMIDA_CROMA"))
    if matriz is False:
        mosqueados = _mosqueados_registrados(h)
        if not any(c is not False for c in mosqueados):
            return ("matriz {} {}/{} não é cor clara admitida pela norma e "
                    "nenhum mosqueado claro foi registrado — sem o arranjo de "
                    "cores do horizonte plíntico".format(
                        h.get("COR_UMIDA_MATIZ"), h.get("COR_UMIDA_VALOR"),
                        h.get("COR_UMIDA_CROMA")))

    return None


def _mosqueados_registrados(h: Horizonte) -> list[bool | None]:
    """Cor clara (V/F/None) de cada mosqueado **registrado** do horizonte.

    Mosqueado sem matiz e sem croma não foi registrado e não entra na lista —
    pela convenção da descrição de campo, é ausência observada. Mosqueado com
    um dos dois entra, e a cor incompleta vale None.
    """
    saida = []
    for i in (1, 2, 3):
        matiz, croma = h.get(f"COR_MOSQ_MATIZ_{i}"), h.get(f"COR_MOSQ_CROMA_{i}")
        if matiz is None and croma is None:
            continue
        saida.append(_cor_clara(matiz, croma))
    return saida


def _e_b(h: Horizonte) -> bool:
    """O horizonte é um B (inclusive BA, BC, `(B)` e grafias que a gramática
    não lê, como `Bw2cn`)?"""
    return principal(h) == "B" or h.simbolo.lstrip("0123456789IVX ()")[:1] == "B"


def _propoe_w(h: Horizonte) -> bool:
    """O símbolo propõe B latossólico (B com sufixo `w`)?"""
    s = gs.analisa(leitura_atual(h.simbolo) or h.simbolo)
    return ((s.principal or "").startswith("B") and not s.mesclado
            and "w" in (x.rstrip(gs.MACRON) for x in s.sufixos))


def _espessura_b_latossolico(perfil: Perfil, h: Horizonte):
    """Espessura mínima do B latossólico: (veto, pendência), um deles ou nenhum.

    🚨 Vigésimo defeito (2026-10-17). A norma exige 50 cm (5ª ed., p. 57), e o
    núcleo não verificava espessura nenhuma do B latossólico. Achado na
    comparação com a linha de base: o sistema de referência aplica os 50 cm
    exatos (sondagem de 2026-10-17: Latossolo com 50, Neossolo com 49).

    Conta-se a **sequência contígua de horizontes B** que contém `h`:
    `W` é a soma dos que propõem B latossólico (sufixo `w`); `T`, a de toda a
    sequência, com BA, BC e B de tipo não legível. Em três valores:

    * `W` >= 50 cm (pela espessura mínima, que admite o horizonte aberto): aprova;
    * `T` >= 50 cm com `W` menor: **pendente** — a norma não diz se BA e BC
      contam (o sistema de referência soma o BA e não o BC; a p. 57 fala em
      "sub-horizontes B (exclusive BC)" noutro requisito, o que sugere que o
      BC é sub-horizonte B);
    * sequência **não fechada** — algum limite desconhecido, lacuna sem
      descrição colada a ela, acima ou abaixo, ou B como último horizonte
      descrito, cuja base é a profundidade de coleta e não o fim do B:
      **pendente**;
    * fechada e `T` < 50 cm: **veto**.
    """
    hs = perfil.horizontes
    i = next((k for k, x in enumerate(hs) if x is h), None)
    if i is None:
        return None, None

    def contiguos(a, b):
        return (a.limite_inf is not None and b.limite_sup is not None
                and a.limite_inf == b.limite_sup)

    ini = fim = i
    while ini > 0 and _e_b(hs[ini - 1]) and contiguos(hs[ini - 1], hs[ini]):
        ini -= 1
    while fim < len(hs) - 1 and _e_b(hs[fim + 1]) and contiguos(hs[fim], hs[fim + 1]):
        fim += 1
    seq = hs[ini:fim + 1]
    minimo = ESPESSURA_MINIMA_B_LATOSSOLICO
    w_min = sum((x.espessura_minima or 0.0) for x in seq if _propoe_w(x))
    if w_min >= minimo:
        return None, None
    esp = [x.espessura for x in seq]
    total = None if None in esp else sum(esp)
    w = sum((x.espessura or 0.0) for x in seq if _propoe_w(x))
    if total is not None and total >= minimo:
        return None, (f"B latossólico com {w:g} cm; os {minimo:g} cm só se "
                      f"alcançam somando BA, BC ou B de tipo não legível "
                      f"({total:g} cm), e a norma não diz se contam")
    fechada_acima = ini == 0 or contiguos(hs[ini - 1], hs[ini])
    fechada_abaixo = fim < len(hs) - 1 and contiguos(hs[fim], hs[fim + 1])
    if total is None or not (fechada_acima and fechada_abaixo):
        motivo = ("limite desconhecido" if total is None else
                  "B como último horizonte descrito" if fim == len(hs) - 1 else
                  "lacuna sem descrição junto ao B")
        return None, (f"espessura do B latossólico não determinada ({motivo}); "
                      f"medidos {w:g} cm, abaixo de {minimo:g}")
    return (f"B latossólico com {total:g} cm (sequência de B fechada), abaixo "
            f"dos {minimo:g} cm mínimos"), None


def _veto_pendente(perfil: Perfil, h: Horizonte, tipo: str) -> str | None:
    """Falta o dado que poderia vetar o que o símbolo propõe? Devolve o quê.

    Só chamado quando `_veto` não vetou. Espelha os dois vetos do plíntico:

    1. **espessura**: pendente quando nem a espessura nem a parte observada
       do horizonte aberto (`espessura_minima`) alcançam 15 cm. O horizonte
       aberto com a profundidade observada na ficha — `RN_042` (110-150+ cm),
       `RN_044` (105-120+ cm) — tem espessura mínima conhecida e não fica
       pendente;
    2. **cor**: pendente quando a matriz não foi registrada e nenhum
       mosqueado claro foi. ⚠️ Matriz registrada sem mosqueado registrado
       **não** fica pendente: descrita a cor do horizonte, a falta de
       mosqueado na descrição é ausência observada, pela convenção da
       descrição de campo — e é o que sustenta o veto do `RN_043`.
    """
    if tipo == "B latossólico":
        return _espessura_b_latossolico(perfil, h)[1]
    if tipo != "plíntico":
        return None
    minima = h.espessura_minima
    if minima is None or minima < ESPESSURA_MINIMA_PLINTICO:
        return ("espessura não determinada" if minima is None else
                f"espessura observada de {minima:g} cm, abaixo de "
                f"{ESPESSURA_MINIMA_PLINTICO:g} cm, num horizonte que continua")
    if _cor_clara(h.get("COR_UMIDA_MATIZ"), h.get("COR_UMIDA_CROMA")) is None:
        mosqueados = [
            _cor_clara(h.get(f"COR_MOSQ_MATIZ_{i}"), h.get(f"COR_MOSQ_CROMA_{i}"))
            for i in (1, 2, 3)
        ]
        if not any(c is True for c in mosqueados):
            return "cor da matriz não registrada e nenhum mosqueado claro"
    # 18º defeito: matriz não clara com mosqueado registrado de cor incompleta.
    elif _cor_clara(h.get("COR_UMIDA_MATIZ"), h.get("COR_UMIDA_CROMA")) is False:
        mosqueados = _mosqueados_registrados(h)
        if not any(c is True for c in mosqueados) and any(c is None for c in mosqueados):
            return "mosqueado registrado sem matiz ou sem croma"
    return None


def _nitico(perfil, h, sufixos, simbolo) -> list[Identificacao]:
    """B nítico: B textural argiloso com cerosidade.

    ✅ Conferido no PDF em 2026-09-07. A norma exige "cerosidade em quantidade
    e grau de desenvolvimento no mínimo **comum e moderado**" — nas escalas do
    contrato, quantidade >= 2 (comum) e grau >= 3 (moderado). Exige também
    textura argilosa (>= 350 g/kg) e relação textural B/A <= 1,5.

    A ausência de policromia nos primeiros 150 cm, que a norma usa para
    separar Nitossolos de Argissolos Vermelhos, continua declarada como
    `Pendente` na regra dos Nitossolos.

    🚨 Vigésimo segundo defeito (2026-10-18), achado pela verificação
    embutida da próxima medição (`nucleo/medicao.py`): preenchida a argila de
    um horizonte que não a tinha, o Nitossolo voltava ao conjunto alcançável
    (`GeoTab_PE_015_Moreno`, sem a granulometria do Bt2). A falta de dado
    refutava por dois caminhos, ambos corrigidos para pendente:

    * argila ausente no próprio horizonte descartava a identificação;
    * a relação textural era calculada só com os horizontes que têm argila,
      e o valor parcial vetava. Faltando argila num horizonte que entra no
      cálculo (`_relacao_textural_completa`), a relação fica indeterminada.

    A cerosidade não registrada **não** identifica o B nítico: é ausência
    observada, pela norma — "Esta característica, quando constatada, deve
    ser descrita no campo" (SiBCS 5ª ed., p. 44; 6ª ed., p. 38, "quando
    verificada"; SANTOS et al., 2015, p. 33, cujos termos são só de
    presença). Decisão do usuário de 2026-10-18 ("regra da norma"), a mesma
    convenção do mosqueado.
    """
    if "t" not in sufixos or not simbolo.principal.startswith("B"):
        return []
    argila = h.get("ARGILA")
    grau = h.get("CEROSIDADE_GRAU")
    quantidade = h.get("CEROSIDADE_QUANTIDADE")
    if argila is not None and float(argila) < 350:
        return []
    # Cerosidade não registrada = não constatada (ausência observada).
    if grau is None or quantidade is None:
        return []
    if float(grau) < 3 or float(quantidade) < 2:
        return []
    # A norma exige, além da cerosidade, relação textural B/A <= 1,5 — o
    # mesmo limite do B latossólico. Verificado no PDF em 2026-09-07.
    rt = relacao_textural(perfil)
    completa = _relacao_textural_completa(perfil)
    if rt is not None and completa and rt > RT_MAXIMA_NITICO:
        return []
    pendencias = []
    if argila is None:
        pendencias.append("argila do horizonte não registrada")
    if not completa:
        pendencias.append("relação textural indeterminada: falta argila num "
                          "horizonte que entra no cálculo")
    if pendencias:
        return [Identificacao(h, "B nítico", "símbolo (veto pendente)",
                              "; ".join(pendencias))]
    return [Identificacao(h, "B nítico", "símbolo",
                          "B textural com argila >= 350 g/kg e cerosidade "
                          f"grau {float(grau):g}, quantidade {float(quantidade):g}")]


def _relacao_textural_completa(perfil: Perfil) -> bool:
    """Todos os horizontes que entram na relação textural têm argila?

    Mesmos horizontes de `relacao_textural` (A inclusive AB; B inclusive BA e
    exclusive BC, na seção de controle), mas tomados **antes** de filtrar os
    que têm argila. Sem horizonte A ou B, ou sem limite para a seção, não há
    o que completar, e a resposta é verdadeira — a relação fica `None`, que
    já não veta.
    """
    def eh_a(h):
        return h.simbolo.replace("/", "")[:1] == "A"

    def eh_b(h):
        return h.simbolo[:1] == "B" and not h.simbolo.startswith("BC")

    a_todos = [h for h in perfil.horizontes if eh_a(h)]
    b_todos = [h for h in perfil.horizontes if eh_b(h)]
    topos = [h.limite_sup for h in b_todos if h.limite_sup is not None]
    if not a_todos or not b_todos or not topos:
        return True
    espessura_a = sum(h.espessura or 0.0 for h in a_todos)
    topo_b = min(topos)
    seccao = 30.0 if espessura_a < 15 else 2.0 * espessura_a
    na_seccao = [h for h in b_todos if h.sobrepoe(topo_b, topo_b + seccao) > 0] or b_todos[:1]
    return all(h.get("ARGILA") is not None for h in a_todos + na_seccao)


def relacao_textural(perfil: Perfil, _horizonte=None) -> float | None:
    """Relação textural B/A conforme a norma, e não por aproximação.

    SiBCS 6ª ed., Cap. 1, atributo "Relação textural B/A", com os três
    exemplos numéricos da Tabela 1.1:

    * média aritmética da argila dos sub-horizontes **A, inclusive AB**;
    * média aritmética da argila dos sub-horizontes **B, inclusive BA e
      exclusive BC**;
    * a média do B é tomada dentro de uma **seção de controle** que começa no
      topo do B e tem 30 cm se o A tiver menos de 15 cm de espessura, ou o
      **dobro da espessura do A** caso contrário;
    * horizonte que apenas começa dentro da seção é incluído por inteiro
      (Exemplo 2 da Tabela 1.1 inclui o Bt2 de 89–150 cm numa seção de
      30–90 cm).

    ⚠️ Esta função substituiu, em 2026-09-07, uma aproximação escrita de
    memória — argila de um único horizonte B sobre a média dos A, com
    transicionais excluídos e limiar variável por textura do A. A aproximação
    não vinha da norma, e produzia dois erros de sinal oposto: vetava o B
    latossólico de `GeoTab_PE_032_Paudalho` (1,53 aproximado contra 1,40
    real) e sustentava uma "correção" que não existia. Ver a nota em
    `[[nucleo-simbolico-classolosbr-ns]]`.
    """
    def argila(h):
        v = h.get("ARGILA")
        return float(v) if v is not None else None

    # "A/B" conta como A; "B/A" conta como B — leitura declarada, a norma não
    # se pronuncia sobre mesclados no cálculo.
    def eh_a(h):
        s = h.simbolo.replace("/", "")
        return s[:1] == "A"

    def eh_b(h):
        s = h.simbolo
        return s[:1] == "B" and not s.startswith("BC")

    horizontes_a = [h for h in perfil.horizontes if eh_a(h) and argila(h) is not None]
    horizontes_b = [h for h in perfil.horizontes if eh_b(h) and argila(h) is not None]
    if not horizontes_a or not horizontes_b:
        return None

    espessura_a = sum(h.espessura or 0.0 for h in horizontes_a)
    # Sem limite superior em nenhum B, não há seção de controle (antes, erro).
    topos = [h.limite_sup for h in horizontes_b if h.limite_sup is not None]
    if not topos:
        return None
    topo_b = min(topos)
    seccao = 30.0 if espessura_a < 15 else 2.0 * espessura_a
    na_seccao = [h for h in horizontes_b if h.sobrepoe(topo_b, topo_b + seccao) > 0]
    if not na_seccao:
        na_seccao = horizontes_b[:1]

    media_a = sum(argila(h) for h in horizontes_a) / len(horizontes_a)
    media_b = sum(argila(h) for h in na_seccao) / len(na_seccao)
    return media_b / media_a if media_a > 0 else None


def mudanca_textural_abrupta(perfil: Perfil) -> Horizonte | None:
    """Primeiro horizonte que apresenta mudança textural abrupta sob si.

    SiBCS 6ª ed., Cap. 1, "Mudança textural abrupta" — verificado no PDF em
    2026-09-07:

        A ou E com argila **< 200 g/kg**  → o B deve ter **pelo menos o dobro**
        A ou E com argila **≥ 200 g/kg**  → incremento **≥ 200 g/kg absoluto**

    ⚠️ Os dois ramos estavam **invertidos** na primeira versão: aplicava-se o
    incremento absoluto ao horizonte arenoso e a duplicação ao argiloso. O
    erro sobrevivia porque ambos os ramos "parecem" o critério, e nenhum
    perfil do conjunto curado o expôs — foi preciso ler a norma.

    ⚠️ Aproximação que permanece declarada: a norma mede o incremento numa
    distância vertical ≤ 7,5 cm, e aqui compara-se o par de horizontes
    contíguos inteiros. Superestima a ocorrência.

    A norma também restringe a transição a **A ou E** sobre B; a versão
    anterior aceitava qualquer par contíguo.
    """
    for i in range(len(perfil.horizontes) - 1):
        cima, baixo = perfil.horizontes[i], perfil.horizontes[i + 1]
        if principal(cima) not in {"A", "E"} or principal(baixo) != "B":
            continue
        a_cima, a_baixo = cima.get("ARGILA"), baixo.get("ARGILA")
        if a_cima is None or a_baixo is None or a_cima <= 0:
            continue
        if float(a_cima) < 200:
            if float(a_baixo) >= 2 * float(a_cima):
                return baixo
        elif float(a_baixo) - float(a_cima) >= 200:
            return baixo
    return None


# ------------------------------------------------------ predicados derivados -
#
# Condições que não cabem numa comparação simples: envolvem posição relativa,
# varredura do perfil ou seção de controle. Cada uma é uma função pequena, com
# citação própria à norma, nomeada por uma condição `Derivado` na regra.
# Todas devolvem `(V3, detalhe)` — e devolvem `I` quando falta dado, nunca `F`.


def _arenoso(h: Horizonte) -> bool | None:
    """Textura arenosa: classes texturais areia e areia franca.

    SiBCS 5ª ed., Cap. 1, p. 46: "Textura arenosa – material que compreende as
    classes texturais areia e areia franca, ou seja, teor de areia menos teor
    de argila > 700 g kg-1". É a mesma fórmula do atributo derivado `ARENOSA`
    (`perfil.py`), usado pelos subgrupos.

    ⚠️ Alinhado à norma em 2026-10-16, por decisão do usuário. Antes, uma
    aproximação própria — areia total ≥ 700 g/kg **e** argila ≤ 150 g/kg —
    divergia da definição. Como areia + argila ≤ 1000 g/kg, a fórmula da norma
    implica areia > 700 e argila < 150: ela é **mais restrita** que a
    aproximação, que aceitava como arenoso, por exemplo, areia 700 e argila 150
    (areia − argila = 550). A mudança só pode tirar horizontes da classe.
    """
    ag, af, argila = h.get("AREIA_GROS"), h.get("AREIA_FINA"), h.get("ARGILA")
    if None in (ag, af, argila):
        return None
    return (float(ag) + float(af)) - float(argila) > 700


def sem_b_diagnostico(perfil: Perfil):
    """Sem qualquer horizonte B diagnóstico — o requisito dos Neossolos.

    SiBCS 6ª ed., Cap. 12: "Neossolos são solos pouco evoluídos [...] não
    apresentando nenhum tipo de horizonte B diagnóstico."
    """
    if tem_b_diagnostico(perfil):
        tipos = sorted({
            i.tipo for i in identificar(perfil)
            if i.valida and i.tipo.startswith("B ")
        })
        return F, "há " + ", ".join(tipos)
    pendentes = b_indeterminados(perfil)
    if pendentes:
        # B cujo tipo o símbolo não diz (notação anterior a 1988, `BW`):
        # pode ser diagnóstico, e o Neossolo não é afirmado nem refutado.
        return I, (", ".join(h.simbolo for h in pendentes)
                   + ": B sem sufixo que designe o tipo — B diagnóstico não decidido")
    return V, "nenhum horizonte B diagnóstico identificado"


def mudanca_textural_abrupta_ocorre(perfil: Perfil):
    """Há mudança textural abrupta entre horizontes contíguos."""
    alvo = mudanca_textural_abrupta(perfil)
    if alvo is not None:
        return V, f"em {alvo.simbolo}"
    faltando = any(h.get("ARGILA") is None for h in perfil.horizontes)
    if faltando:
        return I, "argila ausente em ao menos um horizonte"
    return F, "sem duplicação do teor de argila entre horizontes contíguos"


def _glei_acima(perfil: Perfil, h: Horizonte) -> Horizonte | None:
    """Horizonte glei **mais próximo** acima de `h`, ou `None`.

    Serve à condição (b) dos Plintossolos, cuja frase é "quando precedidos de
    horizonte glei ou situados imediatamente abaixo do horizonte A ou E…": o
    "imediatamente" governa A, E e o horizonte pálido, não o glei (5ª ed.,
    p. 104 e 261; 6ª ed., p. 269). Por isso a busca percorre **todos** os
    horizontes acima de `h`, do mais próximo para o topo.

    Devolve o mais próximo porque é ele que a árvore de prova deve citar: o
    glei que efetivamente precede o plíntico, e não um glei superficial
    separado dele por outros horizontes gleizados. Oitavo defeito
    (2026-10-11); teste: `teste_glei_precedente_nao_imediato`.
    """
    try:
        i = perfil.horizontes.index(h)
    except ValueError:
        return None
    for acima in reversed(perfil.horizontes[:i]):
        if "glei" in tipos_de(perfil, acima):
            return acima
    return None


def _plintico_ate_200_precedido(perfil: Perfil, edicao: str,
                                limite_cm: float = 200,
                                tipos: tuple[str, ...] = (
                                    "plíntico", "concrecionário",
                                    "litoplíntico"),
                                aceita_glei: bool = True):
    """Condição (b) dos Plintossolos, escrita por inteiro.

    Os parâmetros servem ao requisito (c) dos Neossolos da 5ª edição, que
    repete a qualificação do horizonte precedente com outro alcance — 150 cm,
    só o plíntico, sem o glei. Os valores por omissão são os da condição (b).
    Ver `plintico_exclui_neossolo_5ed`.

    SiBCS, Cap. 16: horizonte plíntico, concrecionário ou litoplíntico
    "iniciando dentro de 200 cm a partir da superfície quando precedidos de
    horizonte glei ou situados imediatamente abaixo do horizonte A ou E ou de
    outro horizonte que apresente cores pálidas, variegadas ou com mosqueados
    em quantidade abundante".

    ✅ **Completada em 2026-09-17**, contra os dois PDFs. A versão anterior
    resolvia a parte fácil — glei, A, E — e improvisava o resto: aceitava
    "mosqueado registrado" como se qualquer mosqueado bastasse, e definia
    "cor pálida" por croma ≤ 2 com valor ≥ 5, números que **não estão na
    norma** e que tinham sido apertados à mão para impedir que
    `GeoTab_RN_043_Pedro_Avelino` virasse Plintossolo. O RN_043 era, na
    verdade, problema de identificação do horizonte plíntico (ver `_veto`), e
    o aperto improvisado custava um falso negativo:
    `GeoTab_RN_042_Santo_Antonio`, Plintossolo cujo `Btf` inicia a 110 cm sob
    um `Bt` de cor 10YR 6/3 — pálido pelos dois critérios da norma, refutado
    pelo critério inventado.

    As três formas de qualificar o horizonte precedente pela cor exigem, todas
    elas, que **pelo menos uma cor registrada** satisfaça os itens (a) ou (b)
    da norma. O que as separa é de que jeito a cor foi registrada — e a leitura
    abaixo saiu de `GeoTab_PE_048_Goiana`, que a primeira versão desta função
    tratou como o caso do mosqueado quando é o da coloração variegada:

    * **matriz pálida** → **V**. É a primeira forma, "coloração pálida".
    * **matriz ausente e duas ou mais cores registradas**, uma delas pálida →
      **V**. É a segunda forma, "coloração variegada", em que a norma pede que
      "pelo menos uma das cores" satisfaça aos itens — e é assim que um
      horizonte variegado aparece no contrato: várias cores, matriz nenhuma.
    * **matriz avermelhada ou amarelada com mosqueado pálido** → **I**. Aí, e
      só aí, vale a terceira forma, que exige mosqueados "em quantidade
      abundante (> 20% em volume)" — e **o contrato de entrada não tem campo de
      quantidade de mosqueado**. ⚠️ O BDSolos tem (`Mosqueado - Quantidade`,
      com a classe "Abundante" — 20% ou mais da área pelo IBGE,
      próxima do "> 20% em volume" da norma), mas o adaptador não o
      leva ao contrato; corrigido em 2026-09-18, dizia "nem do acervo". Afirmar seria inventar o dado;
      refutar seria ignorar a norma. A 6ª edição deixa essa condicionante
      explícita: "quando precedidos de horizontes ou camadas **com matriz de
      coloração avermelhada ou amarelada**, mosqueados deverão ocorrer em
      quantidade abundante".
    * nenhuma cor pálida, todas reconhecidas → **F**;
    * cor ausente ou matiz irreconhecível → **I**.
    """
    indeterminacoes: list[str] = []
    candidatos = [(h, False) for t in tipos for h in horizontes_do_tipo(perfil, t)]
    candidatos += [(h, True) for t in tipos
                   for h in horizontes_indeterminados_do_tipo(perfil, t)]
    for h, pendente in candidatos:
            if h.limite_sup is None:
                indeterminacoes.append(
                    f"{h.simbolo} sem limite superior registrado")
                continue
            if h.limite_sup > limite_cm:
                continue
            acima = perfil.acima_de(h)
            if acima is None:
                continue          # na superfície: quem responde é a condição (a)

            onde = f"{h.simbolo} a {h.limite_sup:g} cm"
            # A norma diz "precedidos de horizonte glei" — sem o "imediatamente"
            # que governa A, E e o horizonte pálido. O glei pode estar em
            # qualquer posição acima de `h`, não apenas no horizonte adjacente.
            if pendente:
                # A posição pode satisfazer a condição, mas o horizonte só é
                # plíntico se o dado que falta não o vetar: nunca afirma.
                indeterminacoes.append(
                    f"{onde}: identificação como plíntico com veto pendente")
                continue
            glei = _glei_acima(perfil, h) if aceita_glei else None
            if glei is not None:
                return V, (f"{onde}, precedido do horizonte glei "
                           f"{glei.simbolo}")            
            if principal(acima) in {"A", "E"}:
                return V, f"{onde}, imediatamente abaixo de {acima.simbolo}"

            matriz = _cor_palida_precedente(
                acima.get("COR_UMIDA_MATIZ"), acima.get("COR_UMIDA_VALOR"),
                acima.get("COR_UMIDA_CROMA"), edicao)
            if matriz is True:
                return V, (f"{onde}, sob {acima.simbolo} de cor pálida "
                           f"{acima.get('COR_UMIDA_MATIZ')} "
                           f"{acima.get('COR_UMIDA_VALOR')}/"
                           f"{acima.get('COR_UMIDA_CROMA')}")

            mosqueados = [
                _cor_palida_precedente(
                    acima.get(f"COR_MOSQ_MATIZ_{i}"),
                    acima.get(f"COR_MOSQ_VALOR_{i}"),
                    acima.get(f"COR_MOSQ_CROMA_{i}"), edicao)
                for i in (1, 2, 3)
                if acima.get(f"COR_MOSQ_MATIZ_{i}") is not None
            ]
            registradas = [i for i in (1, 2, 3)
                           if acima.get(f"COR_MOSQ_MATIZ_{i}") is not None]
            if any(c is True for c in mosqueados):
                if matriz is None and len(registradas) >= 2:
                    # Coloração variegada: sem matriz e com mais de uma cor.
                    return V, (f"{onde}, sob {acima.simbolo} de coloração "
                               "variegada com cor pálida entre as registradas")
                indeterminacoes.append(
                    f"{onde}: {acima.simbolo} tem matriz não pálida com "
                    "mosqueado de cor pálida, e a norma exige quantidade "
                    "abundante (> 20% em volume), que o contrato não registra")
                continue
            if matriz is None or any(c is None for c in mosqueados):
                indeterminacoes.append(
                    f"{onde}: cor de {acima.simbolo} ausente ou não reconhecida")
                continue

    if indeterminacoes:
        return I, "; ".join(indeterminacoes)
    return F, "nenhum horizonte plíntico/concrecionário nessa posição"


def plintico_ate_200_precedido_5ed(perfil: Perfil):
    """Condição (b) pela **5ª edição**: item (a) restrito ao matiz 5Y e item
    (b) sem exigência de valor. Ver `_plintico_ate_200_precedido`."""
    return _plintico_ate_200_precedido(perfil, "5")


def plintico_exclui_neossolo_5ed(perfil: Perfil):
    """Requisito (c) dos Neossolos pela **5ª edição** — pela definição, não
    pela chave.

    🚨 Décimo defeito (2026-10-14), achado na revisão da seção 4.2.1 da
    monografia, lendo o texto ao lado do código e da norma. A regra excluía
    o plíntico só "dentro de 40 cm", que é a chave simplificada (p. 111-112),
    enquanto o glei, na mesma regra, já seguia o capítulo. A definição da
    classe (Cap. 3, p. 96) diz:

        "c) Ausência de horizonte plíntico dentro de 40 cm ou dentro de 150 cm
        a partir da superfície se imediatamente abaixo de horizontes A ou E ou
        se precedido de horizontes de coloração pálida, variegada ou com
        mosqueados em quantidade abundante"

    Efeito do defeito: um A seguido de plíntico a 50-150 cm saía NEOSSOLO
    concluído sob a 5ª e PLINTOSSOLO sob a 6ª — diferença que a Camada de
    Versão leria como normativa, e que é de modelagem.

    ⚠️ **A norma diverge de si mesma entre 150 e 200 cm.** O Cap. 3 exclui
    até 150 cm; o Cap. 12 (p. 219) diz, em geral, que o plíntico do Neossolo
    "não ocorre em condição diagnóstica para Plintossolos", e a condição (b)
    dos Plintossolos vai até 200 cm e aceita também o glei precedente. Onde só
    a leitura do Cap. 12 exclui, devolve **I**: a norma não decide, e o
    núcleo não afirma o que a norma não decide.

    V = plíntico na posição que exclui o Neossolo (a regra usa `Nao`).
    """
    for h in horizontes_do_tipo(perfil, "plíntico"):
        if h.limite_sup is not None and h.limite_sup <= 40:
            return V, f"{h.simbolo} a {h.limite_sup:g} cm (dentro de 40 cm)"
    pendentes_40 = [h for h in horizontes_indeterminados_do_tipo(perfil, "plíntico")
                    if h.limite_sup is not None and h.limite_sup <= 40]

    v150, d150 = _plintico_ate_200_precedido(
        perfil, "5", limite_cm=150, tipos=("plíntico",), aceita_glei=False)
    if v150 is V:
        return V, f"{d150} — Cap. 3, requisito (c), até 150 cm"

    v200, d200 = _plintico_ate_200_precedido(
        perfil, "5", limite_cm=200, tipos=("plíntico",), aceita_glei=True)
    if v200 is V:
        return I, (f"{d200}: fora do alcance do Cap. 3 (150 cm, sem glei), "
                   "mas em condição diagnóstica para Plintossolos pelo "
                   "Cap. 12 — a norma diverge de si mesma neste ponto")
    if pendentes_40:
        return I, (f"{pendentes_40[0].simbolo} a {pendentes_40[0].limite_sup:g} cm: "
                   "identificação como plíntico com veto pendente")
    if v150 is I or v200 is I:
        return I, "; ".join(d for v, d in ((v150, d150), (v200, d200))
                            if v is I)
    return F, "nenhum horizonte plíntico em posição que exclua o Neossolo"


def petroplintico_exclui_neossolo_5ed(perfil: Perfil):
    """Concrecionário ou litoplíntico em condição diagnóstica para os
    Plintossolos, na exclusão dos Neossolos pela **5ª edição**.

    🚨 Decisão 3, opção (c), do usuário (2026-10-17). A 5ª diverge de si
    mesma — textos conferidos no PDF em 2026-10-17:

    * a chave (p. 111-112), a Definição dos Neossolos (p. 96-97) e o capítulo
      da ordem (p. 219) excluem dos Neossolos só o horizonte **plíntico**;
    * o Conceito dos Neossolos (p. 96) exclui os solos que atendem aos
      Plintossolos, e a Abrangência dos Plintossolos (p. 104) inclui os
      "Solos Concrecionários" e os "Petroplintossolos" — mas o Conceito dos
      Plintossolos (p. 102-103) exclui, por sua vez, os que atendem aos
      Neossolos: os dois Conceitos são circulares;
    * a 6ª ed. (p. 227) acrescentou concrecionário e litoplíntico à exclusão.

    Como no décimo defeito (plíntico entre 150 e 200 cm), onde só uma das
    leituras exclui, o núcleo não afirma o que a norma não decide: devolve
    **I**, nunca V. Em 2026-10-17, 51 perfis do BDSolos concluíam NEOSSOLO na
    5ª com horizonte concrecionário — 26 rotulados Plintossolo.

    V nunca; I = algum concrecionário ou litoplíntico em posição que atende à
    Definição dos Plintossolos (dentro de 40 cm, ou até 200 cm com a condição
    do horizonte precedente), inclusive com identificação pendente; F = nenhum.
    """
    tipos = ("concrecionário", "litoplíntico")
    rasos = [h for t in tipos
             for h in (*horizontes_do_tipo(perfil, t),
                       *horizontes_indeterminados_do_tipo(perfil, t))
             if h.limite_sup is not None and h.limite_sup <= 40]
    valor, detalhe = _plintico_ate_200_precedido(
        perfil, "5", limite_cm=200, tipos=tipos, aceita_glei=True)
    if rasos:
        detalhe = f"{rasos[0].simbolo} a {rasos[0].limite_sup:g} cm"
    elif valor is F:
        return F, "nenhum concrecionário ou litoplíntico em posição de Plintossolo"
    return I, (f"{detalhe}: a Definição, a chave e o Cap. 12 da 5ª excluem dos "
               "Neossolos só o plíntico; o Conceito (p. 96) e a Abrangência dos "
               "Plintossolos (p. 104) excluem também este horizonte — a norma "
               "diverge de si mesma neste ponto")


def _requisitos_definicao_argissolos(perfil: Perfil, tipos: tuple[str, ...]):
    """Requisitos (a) e (b) da Definição dos Argissolos (Cap. 3).

    🚨 Décimo segundo defeito (2026-10-15), achado quando o usuário trouxe o
    texto integral do Cap. 3 na revisão da monografia: nenhuma das duas bases
    os implementava. A Definição exige, além do B textural:

        a) Horizonte[s] plíntico[, concrecionário ou litoplíntico], se
           presente[s], não está[ão] acima nem é[são] coincidente[s] com a
           parte superficial do horizonte B textural;
        b) Horizonte glei, se presente, não está acima nem é coincidente com
           a parte superficial do horizonte B textural.

    A 5ª (p. 87) lista só o plíntico no item (a); a 6ª (p. 97), plíntico,
    concrecionário e litoplíntico. "Acima ou coincidente com a parte
    superficial" é lido como limite superior menor ou igual ao do primeiro
    B textural. Identificação com veto pendente devolve **I**, nunca F.

    V = requisitos satisfeitos. Na 5ª, em que os Argissolos são a última
    classe, um perfil que a Definição exclua e nenhuma classe anterior
    capture fica sem classe — lacuna da norma, devolvida como tal.
    """
    bts = [h for h in horizontes_do_tipo(perfil, "B textural")
           if h.limite_sup is not None]
    if not bts:
        return V, "sem B textural: requisitos não se aplicam"
    topo = min(h.limite_sup for h in bts)
    violacoes, pendentes = [], []
    for tipo in (*tipos, "glei"):
        for h in horizontes_do_tipo(perfil, tipo):
            if h.limite_sup is not None and h.limite_sup <= topo:
                violacoes.append(f"{tipo} {h.simbolo} a {h.limite_sup:g} cm")
        for h in horizontes_indeterminados_do_tipo(perfil, tipo):
            if h.limite_sup is not None and h.limite_sup <= topo:
                pendentes.append(f"{tipo} {h.simbolo} (veto pendente)")
    if violacoes:
        return F, ("acima ou coincidente com a parte superficial do B "
                   f"textural (topo a {topo:g} cm): " + "; ".join(violacoes))
    if pendentes:
        return I, "; ".join(pendentes)
    return V, "nenhum horizonte excludente acima do topo do B textural"


def requisitos_argissolos_5ed(perfil: Perfil):
    """Requisitos (a) e (b) da Definição pela **5ª edição** (só o plíntico)."""
    return _requisitos_definicao_argissolos(perfil, ("plíntico",))


def requisitos_argissolos_6ed(perfil: Perfil):
    """Requisitos (a) e (b) pela **6ª edição** (plíntico, concrecionário,
    litoplíntico)."""
    return _requisitos_definicao_argissolos(
        perfil, ("plíntico", "concrecionário", "litoplíntico"))


def plintico_ate_200_precedido_6ed(perfil: Perfil):
    """Condição (b) pela **6ª edição**: item (a) estendido aos matizes mais
    acinzentados, esverdeados e azulados, e item (b) com valor ≥ 5. É mais
    larga num extremo e mais estreita no outro. Ver
    `_plintico_ate_200_precedido`."""
    return _plintico_ate_200_precedido(perfil, "6")


def _glei_em_posicao_diagnostica(perfil: Perfil, edicao: str):
    """Posição do horizonte glei exigida pelos Gleissolos, por edição.

    As duas edições aceitam o glei iniciando nos primeiros 50 cm, ou entre 50 e
    150 cm quando imediatamente abaixo de A, E ou hístico com menos de 40 cm.
    ⚠️ **Só a 6ª edição** (Cap. 9) acrescenta que o glei dos primeiros 50 cm
    "deve ocupar a maior parte dos 30 cm imediatamente abaixo do horizonte A".
    A 5ª não tem essa exigência: conferido na chave (Cap. 4, p. 112-113) e no
    capítulo (Cap. 9, p. 175), que dizem apenas "iniciando-se dentro de 50 cm".

    🚨 **Até 2026-09-18 havia um predicado só**, que documentava a 6ª edição e
    era usado também pela base da 5ª — na regra dos Gleissolos e na lista de
    exclusões dos Neossolos. A base de produção aplicava, portanto, uma
    exigência que a norma de produção não faz, e deixava indeterminados dois
    Gleissolos registrados (`GeoTab_PE_025_Barreiros`, `GeoTab_PE_026_Agua_Preta`).
    Foi achado lendo uma árvore de prova real, não por teste. E era invisível à
    auditoria de comparabilidade: um predicado de mesmo nome nas duas bases tem
    estrutura idêntica. Daí os dois predicados, um por edição.
    """
    gleis = horizontes_do_tipo(perfil, "glei")
    if not gleis:
        return F, "nenhum horizonte glei"
    for g in gleis:
        if g.limite_sup is None:
            continue
        topo = g.limite_sup
        if topo <= 50:
            if edicao == "5":
                return V, f"{g.simbolo} inicia a {topo:g} cm (dentro dos 50 cm)"
            base_a = max(
                (h.limite_inf for h in perfil.horizontes
                 if principal(h) == "A" and h.limite_inf is not None),
                default=0.0,
            )
            faixa = (base_a, base_a + 30)
            ocupado = sum(x.sobrepoe(*faixa) for x in gleis)
            if ocupado > 15:
                return V, (f"{g.simbolo} inicia a {topo:g} cm e ocupa "
                           f"{ocupado:g} dos 30 cm abaixo do A")
            # ⚠️ Perfis com lacuna na descrição (trechos de profundidade sem
            # horizonte descrito) não permitem medir a ocupação. Refutar aí
            # seria transformar ausência de descrição em ausência de glei.
            # Observado em `GeoTab_PE_025_Barreiros`: Ap 0-15, Cg1 30-50 — os
            # 15 cm não descritos decidiriam a classe.
            descrito = sum(x.sobrepoe(*faixa) for x in perfil.horizontes)
            if descrito < 30:
                return I, (f"{30 - descrito:g} cm dos 30 abaixo do A não têm "
                           "horizonte descrito — ocupação não mensurável")
            return F, (f"{g.simbolo} inicia a {topo:g} cm mas ocupa apenas "
                       f"{ocupado:g} dos 30 cm abaixo do A")
        if 50 < topo <= 150:
            acima = perfil.acima_de(g)
            if acima is None:
                continue
            letra = principal(acima)
            if letra in {"A", "E"}:
                return V, f"{g.simbolo} a {topo:g} cm, imediatamente abaixo de {acima.simbolo}"
            if letra == "H" and (acima.espessura or 0) < 40:
                return V, f"{g.simbolo} a {topo:g} cm, sob hístico delgado"
    return F, "glei fora da posição diagnóstica"


def glei_em_posicao_diagnostica_5ed(perfil: Perfil):
    """Posição do glei pela **5ª edição**: sem a exigência dos 30 cm."""
    return _glei_em_posicao_diagnostica(perfil, "5")


def glei_em_posicao_diagnostica_6ed(perfil: Perfil):
    """Posição do glei pela **6ª edição**: o glei dos primeiros 50 cm ocupa a
    maior parte dos 30 cm abaixo do A."""
    return _glei_em_posicao_diagnostica(perfil, "6")


#: Profundidade da exclusão textural dos Gleissolos, por edição. A 5ª (Cap. 9)
#: diz "até a profundidade de 150 cm"; a 6ª (Cap. 9) diz "até a profundidade de
#: 200 cm". Diferença de norma, conferida nos dois PDFs em 2026-09-17.
PROFUNDIDADE_EXCLUSAO_ARENOSA = {"5": 150.0, "6": 200.0}


def _sem_textura_areia_exclusiva(perfil: Perfil, edicao: str):
    """A exclusão textural dos Gleissolos **não** se aplica a este perfil?

    SiBCS, Cap. 9: os Gleissolos não têm "classe textural areia ou areia franca
    **em todos os horizontes**" até a profundidade da edição.

    🚨 **O quantificador estava invertido** até 2026-09-17, e o defeito era
    invisível na leitura corrida do código: a função refutava no **primeiro**
    horizonte arenoso que encontrasse, quando a norma só exclui o perfil se
    **todos** forem arenosos. Um único horizonte arenoso no fundo do perfil
    bastava para negar a classe.

    Custou `GeoTab_RN_021_Ceara_Mirim`, Gleissolo cujo terceiro horizonte tem
    80 g/kg de argila: o `AP` tem 330 e o horizonte glei tem 360, de modo que o
    perfil está longe de ser "exclusivamente arenoso" — e era negado por causa
    do horizonte de baixo. Foi a última violação de contenção do conjunto
    curado.

    Devolve **V** quando ao menos um horizonte na seção não é arenoso (a
    exclusão não se aplica), **F** quando todos são, e **I** quando o que falta
    para decidir é granulometria.
    """
    limite = PROFUNDIDADE_EXCLUSAO_ARENOSA[edicao]
    na_secao = [h for h in perfil.horizontes
                if h.limite_sup is None or h.limite_sup <= limite]
    if not na_secao:
        return V, f"nenhum horizonte descrito até {limite:g} cm"

    desconhecidos = []
    for h in na_secao:
        arenoso = _arenoso(h)
        if arenoso is False:
            return V, (f"{h.simbolo} não tem textura arenosa, logo a textura "
                       f"não é exclusivamente areia até {limite:g} cm")
        if arenoso is None:
            desconhecidos.append(h.simbolo)
    if desconhecidos:
        return I, ("granulometria ausente em " + ", ".join(desconhecidos)
                   + " — não se decide se a textura arenosa é exclusiva")
    return F, (f"todos os horizontes até {limite:g} cm têm textura areia ou "
               "areia franca")


def sem_textura_areia_exclusiva_5ed(perfil: Perfil):
    """Exclusão textural dos Gleissolos pela **5ª edição**: seção de 150 cm."""
    return _sem_textura_areia_exclusiva(perfil, "5")


def sem_textura_areia_exclusiva_6ed(perfil: Perfil):
    """Exclusão textural dos Gleissolos pela **6ª edição**: seção de 200 cm."""
    return _sem_textura_areia_exclusiva(perfil, "6")


def _base_conhecida(h: Horizonte) -> float | None:
    if h.limite_inf is None or h.limite_inf >= INDETERMINADA:
        return None
    return h.limite_inf


def requisito_espessura_chernozemico(perfil: Perfil):
    """Espessura exigida do A chernozêmico — item (e) da definição.

    SiBCS 5ª ed., p. 51; 6ª ed., p. 61 — texto conferido no PDF em 2026-10-17:

        Espessura, incluindo horizontes transicionais (tais como AB, AE ou
        AC) [...] de acordo com um dos seguintes requisitos:
        1) 10 cm ou mais, se o horizonte A é seguido de contato com a rocha;
        2) 18 cm (no mínimo) e mais que um terço da espessura do solum (A+B,
           inclusive BC [6ª ed.]), se este tiver menos que 75 cm;
        3) para solos sem horizonte B, 18 cm no mínimo e mais de um terço da
           espessura dos horizontes A+C, se esta for inferior a 75 cm;
        4) 25 cm (no mínimo), se o solum tiver 75 cm ou mais de espessura.

    Devolve ``(brando, exigente, descricao)``, cada requisito um par
    ``(minimo_cm, terco_cm | None)``. Os dois coincidem quando a norma decide;
    divergem quando o dado ou a norma não decidem, e o que cai entre eles é
    indeterminado.

    🚨 Décimo sexto defeito (2026-10-17). A versão anterior devolvia 18 ou
    25 cm e comparava com **cada** horizonte A isolado: não somava os
    sub-horizontes, não aplicava o terço (ramos 2 e 3) nem o ramo 1, e media o
    solum somando só os horizontes descritos — um intervalo sem descrição
    encolhia o solum. Agora o solum é medido por profundidade.

    Decisões de leitura (registradas no log de 2026-10-17):
    * ramo 1: contato com a rocha = horizonte R logo abaixo do último
      sub-horizonte A (o contrato não informa contato lítico; o símbolo R é a
      evidência disponível);
    * solum: A+B inclusive BC também na 5ª ed., que só diz "A+B" — a 6ª
      explicita o que a 5ª deixa implícito;
    * sem B e A+C ≥ 75 cm (ou de base aberta): a norma não tem ramo. O mínimo
      fica entre 18 e 25 cm e o que cai entre os dois é indeterminado — o
      núcleo não afirma o que a norma não decide.
    """
    hs = perfil.horizontes
    idx_a = [k for k, h in enumerate(hs) if principal(h) == "A"]
    if idx_a and idx_a[-1] + 1 < len(hs) and principal(hs[idx_a[-1] + 1]) == "R":
        return (10.0, None), (10.0, None), "A seguido de contato com a rocha (R): 10 cm"
    # O solum começa na superfície mineral: o orgânico posto acima dela
    # (19º defeito) não entra na conta.
    topo = min((h.limite_sup for h in hs if h.limite_sup is not None
                and principal(h) not in ("O", "H")), default=0.0)
    bs = [h for h in hs if principal(h) == "B" and h.limite_sup is not None]
    if bs:
        bases = [_base_conhecida(h) for h in bs]
        if None not in bases:
            solum = max(bases) - topo
            if solum >= 75:
                return (25.0, None), (25.0, None), f"solum de {solum:g} cm: 25 cm"
            r = (18.0, solum / 3)
            return r, r, f"solum de {solum:g} cm: 18 cm e mais de {solum / 3:.1f} cm"
        piso = max(h.limite_sup for h, b in zip(bs, bases) if b is None) - topo
        if piso >= 75:
            return (25.0, None), (25.0, None), f"solum de {piso:g} cm ou mais: 25 cm"
        return ((18.0, piso / 3), (25.0, None),
                f"solum de base aberta (≥ {piso:g} cm): entre 18 e 25 cm")
    cs = [h for h in hs if principal(h) in ("A", "C") and h.limite_sup is not None]
    bases = [_base_conhecida(h) for h in cs]
    if cs and None not in bases and max(bases) - topo < 75:
        ac = max(bases) - topo
        r = (18.0, ac / 3)
        return r, r, f"sem B, A+C de {ac:g} cm: 18 cm e mais de {ac / 3:.1f} cm"
    return ((18.0, None), (25.0, None),
            "sem B, A+C de 75 cm ou mais ou de base aberta (a norma não tem "
            "ramo para o caso): entre 18 e 25 cm")


def atende_espessura(espessura: float, requisito) -> bool:
    minimo, terco = requisito
    return espessura >= minimo and (terco is None or espessura > terco)


def a_chernozemico(perfil: Perfil):
    """Horizonte A chernozêmico.

    SiBCS 5ª ed., p. 50-51 (6ª ed., p. 60-61). Exige, conjugadamente:
    estrutura ao menos moderada, cor úmida com valor e croma ≤ 3, saturação
    por bases ≥ 65%, carbono orgânico ≥ 6 g/kg "em todo o horizonte" e a
    espessura do item (e), que inclui os horizontes transicionais.

    ⚠️ Ajustado em 2026-09-07. A primeira versão exigia apenas cor, V% e
    espessura ≥ 10 cm, e **afirmava** A chernozêmico em Luvissolos e
    Cambissolos de região semiárida — cinco falsos positivos no conjunto
    curado. Critério frouxo num predicado que alimenta uma classe de alta
    precedência contamina tudo o que vem depois dela na chave.

    🚨 Corrigido em 2026-10-12. O limiar de estrutura era `>= 2`, que na escala
    do contrato (ausente 1, fraca 2, moderada 3, forte 4) aceita estrutura
    **fraca**. A norma exige grau "predominantemente moderado ou forte"
    (5ª ed., item a do A chernozêmico; 6ª ed., p. 60-61): o limiar é `>= 3`,
    o mesmo que `cerosidade_suficiente` já usa para "moderado".

    ⚠️ Fora do contrato ou não implementado (registrado em 2026-10-17): valor
    da cor seca ≤ 5; predomínio de Ca e/ou Mg no complexo sortivo; exclusão de
    estrutura maciça com consistência dura; exceção do carbonato (≥ 400 g/kg
    de CaCO3 equivalente).
    """
    # 🚨 Décimo quinto defeito (2026-10-16), achado ao procurar um caso real
    # de dado ausente para a §4.4 da monografia. Bastava faltar um componente
    # em algum horizonte A para o predicado devolver **indeterminado**, mesmo
    # que outro componente presente já reprovasse aquele horizonte — e a
    # conjunção da norma ("conjugadamente") é falsa com um termo falso. Agora
    # cada sub-horizonte A é avaliado pela regra de Kleene: reprovado se algum
    # componente presente reprova; incompleto se nenhum reprova e algum falta;
    # aprovado se todos aprovam. A pendência nomeia o que falta, por horizonte
    # — a orientação de coleta da §4.2.4.
    #
    # 🚨 Décimo sexto defeito (2026-10-17): a espessura é a **soma** dos
    # sub-horizontes A (inclusive AB, AE e AC) que aprovam, contra o
    # requisito do item (e) — ver `requisito_espessura_chernozemico`. O que
    # reprova fica fora da soma: é a leitura do curador do conjunto PYKKA7 em
    # `GeoTab_PE_028_Sirinhaem` ("o Apg tem [estrutura] fraca. Então resta
    # testar o Ap"), e a soma não precisa começar na superfície
    # (`GeoTab_PE_020_Macaparana`, Ap fraco sobre A2 e A3 moderados, rotulado
    # Chernossolo). O SmartSolos soma também os que reprovam e não aplica o
    # terço — verificado na API em 2026-10-17 com nove versões de
    # `GeoTab_RN_019_Apodi`; o núcleo segue a norma (decisão do usuário).
    criterios = (
        ("COR_UMIDA_VALOR", "valor da cor úmida", lambda x: float(x) <= 3),
        ("COR_UMIDA_CROMA", "croma da cor úmida", lambda x: float(x) <= 3),
        ("V_PERCENT", "saturação por bases (V%)", lambda x: float(x) >= 65),
        ("C_ORG", "carbono orgânico", lambda x: float(x) >= 6),
        ("ESTRUTURA_GRAU", "grau de estrutura", lambda x: float(x) >= 3),
    )
    aprovados, pendentes = [], []
    soma_aprovada = soma_incompleta = 0.0
    sem_espessura = False
    for h in perfil.horizontes:
        if principal(h) != "A":
            continue
        valores = [(nome, h.get(campo), teste) for campo, nome, teste in criterios]
        if any(x is not None and not teste(x) for _, x, teste in valores):
            continue                                   # reprovado: fora da soma
        faltam = [nome for nome, x, _ in valores if x is None]
        if h.espessura is None:
            faltam.append("espessura (limites do horizonte)")
            sem_espessura = True
        if faltam:
            pendentes.append(f"{h.simbolo}: falta {', '.join(faltam)}")
            soma_incompleta += h.espessura or 0.0
            continue                                   # incompleto
        aprovados.append(h)
        soma_aprovada += h.espessura
    # 13º defeito (2026-10-15): a lista dos componentes que tornam o A
    # incompleto tem de ser a mesma dos que o aprovam — garantido agora por
    # construção, porque as duas leituras saem da mesma tabela `criterios`.
    brando, exigente, regra = requisito_espessura_chernozemico(perfil)
    if aprovados and atende_espessura(soma_aprovada, exigente):
        partes = " + ".join(f"{h.simbolo} {h.espessura:g} cm" for h in aprovados)
        return V, (f"{partes} atendem cor, V, C orgânico e estrutura; "
                   f"{soma_aprovada:g} cm ({regra})")
    teto = float("inf") if sem_espessura else soma_aprovada + soma_incompleta
    if (aprovados or pendentes) and atende_espessura(teto, brando):
        motivo = ("; ".join(pendentes) if pendentes else
                  f"{soma_aprovada:g} cm, na faixa que a norma não decide")
        return I, f"evidência incompleta no horizonte A — {motivo} ({regra})"
    if not aprovados and not pendentes:
        return F, ("nenhum A reúne cor escura, C orgânico, estrutura e saturação "
                   "por bases nos patamares do A chernozêmico")
    return F, (f"os sub-horizontes A que atendem cor, V, C orgânico e estrutura "
               f"somam {soma_aprovada:g} cm"
               f"{f' (mais {soma_incompleta:g} cm incompletos)' if soma_incompleta else ''}"
               f", abaixo do exigido ({regra})")


#: Registro consultado pela condição `Derivado`. O nome na regra é a chave.
PREDICADOS = {
    "sem horizonte B diagnóstico": sem_b_diagnostico,
    "mudança textural abrupta": mudanca_textural_abrupta_ocorre,
    "plíntico até 200 cm em posição diagnóstica (5ª ed.)":
        plintico_ate_200_precedido_5ed,
    "plíntico até 200 cm em posição diagnóstica (6ª ed.)":
        plintico_ate_200_precedido_6ed,
    "glei em posição diagnóstica (5ª ed.)": glei_em_posicao_diagnostica_5ed,
    "glei em posição diagnóstica (6ª ed.)": glei_em_posicao_diagnostica_6ed,
    "sem textura areia exclusiva até 150 cm (5ª ed.)":
        sem_textura_areia_exclusiva_5ed,
    "sem textura areia exclusiva até 200 cm (6ª ed.)":
        sem_textura_areia_exclusiva_6ed,
    "horizonte A chernozêmico": a_chernozemico,
    "plíntico em posição que exclui o Neossolo (5ª ed.)":
        plintico_exclui_neossolo_5ed,
    "concrecionário ou litoplíntico em posição de Plintossolo (5ª ed.)":
        petroplintico_exclui_neossolo_5ed,
    "requisitos (a) e (b) da Definição dos Argissolos (5ª ed.)":
        requisitos_argissolos_5ed,
    "requisitos (a) e (b) da Definição dos Argissolos (6ª ed.)":
        requisitos_argissolos_6ed,
}
