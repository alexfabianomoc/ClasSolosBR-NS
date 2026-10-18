"""Gramática dos símbolos de horizonte — validação de anotação.

Formaliza a norma de notação de horizontes e camadas para que um símbolo
anotado (`Ap`, `Bt2`, `2Cg1`, `Btb`, `E'`) possa ser verificado quanto à
boa-formação, e não apenas lido como rótulo opaco.

Isso importa porque `SIMB_HORIZ` **não é rótulo descritivo**: é a entrada que
decide a classe no motor de referência (SmartSolos). Símbolo malformado não
produz erro — produz classificação errada em silêncio.

Fonte normativa
---------------
LARACH, J. O. I.; CAMARGO, M. N.; JACOMINE, P. K. T.; CARVALHO, A. P. de;
SANTOS, H. G. dos. *Definição e notação de horizontes e camadas do solo*.
2. ed. rev. e atual. Rio de Janeiro: EMBRAPA-SNLCS, 1988. 54 p. (Documentos, 3)
— **a fonte primária**: súmula de sufixos (p. 27-28) e, no Anexo 1, os mapas
normativos de correspondência entre a notação anterior e a atual. Acesso aberto
(CC BY-NC-ND 4.0). 1ª ed.: SANTOS et al., 1983, 34 p.

LEMOS, R. C. de; SANTOS, R. D. dos. *Manual de descrição e coleta de solo no
campo*. 3. ed. Campinas: SBCS, 1996. 84 p. — súmula de sufixos (p. 47-48) e
tabela de aplicabilidade por horizonte principal (p. 49). A obra transcreve as
"definições completas formalizadas pelos pesquisadores da EMBRAPA/CNPS", e é
uma das duas a que a 6ª edição do SiBCS remete: o SiBCS **usa** este
vocabulário mas não o define.

Cotejo com IBGE. *Manual técnico de pedologia*. 3. ed. Rio de Janeiro, 2015,
itens 1.1.5.3-1.1.5.4, que documenta o mesmo vocabulário sob a 3ª edição do
SiBCS (2013).

⚠️ O sufixo `k̄` e por que ele quase sempre já se perdeu
--------------------------------------------------------
A norma distingue dois sufixos de carbonato por **uma barra sobre a letra**:

    k   presença de carbonatos herdados, sem acumulação
    k̄   acumulação de carbonato de cálcio secundário
        (≥ 150 g·kg⁻¹ de CaCO₃ equivalente E ≥ 50 g·kg⁻¹ a mais que o
        horizonte subjacente, o C, ou o material de origem)

`k̄` exige `k` + COMBINING MACRON (U+0304). Em ASCII os dois colapsam, e com
eles duas condições diagnósticas distintas. Medido em 2026-09-07: **zero**
ocorrências de U+0304 no PYKKA7 (96 JSON), no BDSolos e no PDF da 6ª edição do
SiBCS. Nenhum corpus disponível preservou a distinção.

⚠️ `_sanear()` do DAG Bronze faz `NFKD → encode("ascii", "ignore")`. Hoje só
roda sobre **nomes de coluna**. Aplicá-lo a valores destruiria `k̄` sem deixar
traço — ver `suspeita_k_barra_perdido()`, que é a única defesa possível depois
que o dado chega.

⚠️ A gramática é versionada
---------------------------
1996 e 2015 divergem, e a norma de 1996 é internamente inconsistente (a súmula
diz que `z` serve a `O`; a tabela de aplicabilidade da p. 49 não lista `z` em
`O`). Por isso sufixo fora da tabela é **alerta**, não erro: a norma não
sustenta rejeição categórica. Ver `DIVERGENCIAS`.

Sem dependências além da stdlib — roda dentro de UDF Spark, de task Airflow ou
da linha de comando.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

MACRON = "̄"
K_BARRA = "k" + MACRON

# ⚠️ Segunda distinção que o texto simples não carrega — e pior que a do mácron.
# A 7ª edição distingue `f` de `ƒ` **por estilo tipográfico**: redondo × itálico.
#   f  (redondo)  presença de plintita
#   ƒ  (itálico)  feições ferruginosas em geral — segregação de Fe/Al que produz
#                 mosqueados, sem chegar a constituir plintita
# Itálico não é caractere: é fonte. Em CSV, JSON ou coluna de banco os dois são
# o MESMO `f`, e nem existe o recurso que o mácron ainda oferece (`k`+U+0304).
# Adota-se aqui U+0192 (ƒ) como representação canônica — é convenção de
# transcrição, não a grafia da norma.
F_CURSIVO = "ƒ"

# Limiar de CaCO₃ equivalente (g·kg⁻¹) na definição de `k̄`. O segundo critério
# da norma — ≥ 50 a mais que o horizonte subjacente — precisa do perfil inteiro
# e é aplicado em `suspeita_k_barra_perdido` quando o vizinho é informado.
LIMIAR_CACO3 = 150.0
DELTA_CACO3 = 50.0

# Horizontes e camadas principais (Lemos & Santos, 1996, p. 38).
PRINCIPAIS = ("O", "H", "A", "E", "B", "C", "F", "R")

# Horizontes transicionais (p. 39): duas maiúsculas, predominando a primeira.
# ⚠️ Não confundir com sufixo maiúsculo — `AB` é transicional A→B, não `A` com
# sufixo `B`. Sem esta lista, 13% do PYKKA7 vira falso positivo.
TRANSICIONAIS = frozenset({
    "AB", "AE", "AC", "EA", "EB", "BA", "BE", "BC", "CB", "CA",
})

# Semântica de cada sufixo. Chave é a notação canônica.
SUFIXOS: dict[str, str] = {
    "a": "propriedades ândicas",
    "b": "horizonte enterrado",
    "c": "concreções ou nódulos endurecidos",
    "d": "acentuada decomposição de material orgânico",
    "e": "escurecimento externo dos agregados por matéria orgânica",
    "f": "material plíntico e/ou bauxítico brando (plintita)",
    F_CURSIVO: "feições ferruginosas em geral (segregação de Fe/Al sem plintita)",
    "g": "glei",
    "h": "acumulação iluvial de matéria orgânica",
    "i": "incipiente desenvolvimento de horizonte B",
    "j": "tiomorfismo",
    "k": "presença de carbonatos",
    K_BARRA: "acumulação de carbonato de cálcio secundário",
    "m": "extremamente cimentado",
    "n": "acumulação de sódio trocável",
    "o": "material orgânico mal ou não decomposto",
    "p": "aração ou outras pedoturbações",
    "q": "acumulação de sílica",
    "r": "rocha branda ou saprolito",
    "s": "acumulação iluvial de sesquióxidos com matéria orgânica",
    "t": "acumulação de argila",
    "u": "modificações e acumulações antropogênicas",
    "v": "características vérticas",
    "w": "intensa alteração com inexpressiva acumulação de argila",
    "x": "cimentação aparente, reversível",
    "y": "acumulação de sulfato de cálcio",
    "z": "acumulação de sais mais solúveis em água fria que sulfato de cálcio",
    # Só a partir do vocabulário de 2015 (ausentes em 1996).
    "do": "material orgânico intermediário entre d e o, predominando d",
    "od": "material orgânico intermediário entre d e o, predominando o",
    "qm": "acumulação de sílica com cimentação contínua",
}

# Tabela de aplicabilidade: quais sufixos cada horizonte principal admite.
#
# `1996` transcreve Lemos & Santos, p. 49. Duas notas de transcrição:
#   - a linha `C` sai impressa como "...v, x, y, x, r": `x` duas vezes e `z`
#     ausente. Lido como `z` porque a súmula da p. 47 diz, no verbete de `z`,
#     "Usado com O, A, B, C". Divergência registrada em DIVERGENCIAS.
#   - `R` não aparece na tabela: a norma diz que todos os principais devem
#     receber sufixo "exceto R e algumas vezes C, E".
APLICABILIDADE: dict[str, dict[str, frozenset[str]]] = {
    "1996": {
        # ⚠️ {"d", "o"} — dois sufixos simples, não o composto "do".
        # `do`/`od` acrescentados a partir da fonte primária: Larach et al.
        # (1988, p. 27) reconhece `Hdo`, `Hod`, `Odo` e `Ood` como horizontes
        # transicionais de matéria orgânica em decomposição intermediária. A
        # tabela de Lemos & Santos (1996, p. 49) os omite; a norma anterior e o
        # IBGE (2015) os trazem, então a omissão é que é a exceção.
        "O": frozenset({"d", "o", "do", "od"}),
        "H": frozenset({"d", "j", "n", "o", "p", "u", "z", "do", "od"}),
        "A": frozenset({"a", "b", "c", "e", "f", "g", "k", K_BARRA,
                        "n", "p", "u", "z"}),
        "E": frozenset({"b", "c", "g", "x"}),
        "B": frozenset({"a", "b", "c", "e", "f", "g", "j", "k", K_BARRA,
                        "m", "n", "q", "v", "x", "y", "z",
                        "h", "i", "s", "t", "w"}),
        # ⚠️ Sem `z`, e com uma duplicata NÃO RESOLVIDA.
        #
        # A linha impressa é "a, c, f, g, j, k, k, m, n, q, v, x, y, x, r":
        # `x` duas vezes, `k` duas vezes, nenhum `z`. Já errei duas leituras
        # dela — nenhuma das duas hipóteses se sustenta:
        #   · "a duplicata de `x` é erro de impressão por `z`" — refutada: a 7ª
        #     edição corrigiu REMOVENDO, sem acrescentar `z`;
        #   · "duplicata é erro de composição" — presunçosa, já que o `k` duplo
        #     da mesma linha É significativo (`k` e `k̄`).
        #
        # 🚨 O que a inspeção da página estabelece: **esta tabela não reproduz
        # os diacríticos**. O segundo `k` aparece aqui sem a barra, embora a
        # súmula da p. 47 grafe `k̄`. A tabela é, portanto, uma renderização com
        # perda — dentro do próprio livro impresso. Não serve para decidir
        # distinções tipográficas, e pode estar ocultando outras.
        #
        # A súmula (p. 47-48), que é a lista definidora, traz **um único** `x`.
        # Se o segundo é um sufixo distinto, ele não tem verbete. Fica em aberto.
        "C": frozenset({"a", "c", "f", "g", "j", "k", K_BARRA,
                        "m", "n", "q", "v", "x", "y", "r"}),
        "F": frozenset({"b"}),
        "R": frozenset(),
    },
}

# 2015 (IBGE) = 1996 mais as diferenças abaixo. Construída por delta para que a
# divergência fique explícita no código, e não escondida em duas listas.
DIVERGENCIAS: dict[str, str] = {
    "p em O": "ÚNICA alteração substantiva da tabela entre a 3ª ed. (1996) e a "
              "7ª (2015): `p` foi acrescentado a `O`. Confirma o IBGE (2015).",
    "b em O": "o IBGE (2015) afirma que `b` serve a O; a tabela da 7ª edição "
              "NÃO o lista — a prosa do IBGE e a tabela da SBCS discordam",
    "u em O": "idem `b`: IBGE afirma, tabela da 7ª edição não lista",
    "j em A": "idem: IBGE afirma (H, A, B, C), tabela da 7ª edição não lista",
    "z em C": "prosa e tabela discordam nas DUAS edições. A 7ª edição corrigiu "
              "o alcance (prosa de 1996: 'O, A, B, C'; prosa de 2015: 'H, A, B "
              "e C' — trocou O por H, coerente com as tabelas), mas manteve a "
              "contradição em `C`: a prosa inclui C, a tabela não lista `z`.",
    "x duplicado em C": "EM ABERTO, e mais intrigante do que parecia. A linha C "
                        "traz `x` duas vezes na 3ª edição (p. 49) E na 7ª "
                        "(p. 53) — sobreviveu a uma revisão ampliada. Mas "
                        "nenhuma das duas súmulas define um segundo `x`. Nem "
                        "erro de composição (persistiu) nem sufixo documentado "
                        "(sem verbete).",
    "ƒ sem verbete": "espelho do caso do `k̄`, e igualmente sistemático: na 7ª "
                     "edição `ƒ` aparece na TABELA (p. 53) mas NÃO na súmula "
                     "(p. 52), enquanto `k̄` aparece na SÚMULA e não na tabela. "
                     "Cada variante tipográfica está documentada em exatamente "
                     "um dos dois lugares, nunca nos dois.",
    "tabela não carrega o k̄": "🚨 CONFIRMADO NAS DUAS EDIÇÕES, de formas "
                              "diferentes. 3ª ed.: a tabela (p. 49) grafa o "
                              "segundo `k` SEM a barra, embora a súmula (p. 47) "
                              "traga `k̄`. 7ª ed.: a súmula (p. 52) traz `k̄`, "
                              "e a tabela (p. 53) simplesmente NÃO o lista. "
                              "Duas edições, 19 anos, o mesmo defeito: a tabela "
                              "de aplicabilidade não carrega o diacrítico. Não "
                              "é lapso de composição — é sistemático, e a "
                              "tabela não decide questões tipográficas.",
    "z em O": "RESOLVIDO na 7ª edição: a prosa de 1996 dizia 'O, A, B, C'; a de "
              "2015 diz 'H, A, B e C'. O `O` saiu, o `H` entrou — agora a prosa "
              "concorda com as tabelas nesse ponto.",
    "do/od": "a tabela de 1996 (p. 49) os omite, mas Larach et al. (1988, "
             "p. 27) os reconhece como horizontes transicionais em O e H, e o "
             "IBGE (2015) também — a omissão de 1996 é a exceção",
    "qm": "presente no IBGE (2015); NÃO verificado na 7ª edição — a tabela de "
          "aplicabilidade não o menciona e a questão segue em aberto",
    "f × ƒ": "a 7ª edição distingue plintita (`f` redondo) de feições "
             "ferruginosas (`ƒ` itálico) por TIPOGRAFIA. Distinção "
             "irrecuperável em texto simples, e sem o recurso que o mácron "
             "oferece — itálico não é caractere.",
    "k̄ na 7ª edição": "RESOLVIDO: `k̄` CONSTA da súmula da 7ª edição (p. 52) — "
                      "não foi suprimido do vocabulário. Mas NÃO consta da "
                      "tabela de aplicabilidade (p. 53). A tabela, portanto, "
                      "não diz a quais horizontes ele se aplica; a atribuição a "
                      "A, B e C aqui é herdada da 3ª edição.",
}

# 7ª edição do Manual de descrição e coleta de solo no campo (SANTOS et al.,
# 2015, p. 53), cotejada linha a linha contra a 3ª edição.
#
# Alterações verificadas contra a 3ª edição:
#   · `p` acrescentado a `O`;
#   · `ƒ` (itálico) acrescentado a `A`, `B` e `C`;
#   · a duplicata de `x` na linha `C` **PERMANECE** — sobreviveu 19 anos e uma
#     edição revista e ampliada. Isso enfraquece muito a leitura de "erro de
#     composição": dois prelos independentes imprimem `x` duas vezes.
#
# ⚠️ Esta tabela **não** é a prosa do Manual técnico de pedologia do IBGE
# (2015). São documentos distintos e discordam: o IBGE diz que `b`, `p` e `u`
# servem a `O` e que `j` serve a `A`; a 7ª edição confirma apenas o `p`.
APLICABILIDADE["2015"] = {
    "O": APLICABILIDADE["1996"]["O"] | {"p"},
    "H": APLICABILIDADE["1996"]["H"],
    # ⚠️ `k̄` aqui é HERANÇA DE 1996, não leitura da 7ª edição. A súmula da 7ª
    # (p. 52) **define** `k̄`; a tabela de aplicabilidade (p. 53) **não o lista**.
    # Logo o sufixo é válido na 7ª edição, mas ela não diz a quais horizontes se
    # aplica. Mantidos A, B e C por continuidade com a 3ª edição.
    "A": APLICABILIDADE["1996"]["A"] | {F_CURSIVO},
    "E": APLICABILIDADE["1996"]["E"],
    "B": APLICABILIDADE["1996"]["B"] | {F_CURSIVO},
    "C": APLICABILIDADE["1996"]["C"] | {F_CURSIVO},
    "F": APLICABILIDADE["1996"]["F"],
    "R": APLICABILIDADE["1996"]["R"],
}

EDICAO_PADRAO = "1996"

# Sufixos com precedência quando cabe mais de um (1996, p. 49).
PRECEDENCIA = ("d", "i", "o", "h", "s", "t", "u", "r", "w")

# Sufixos de duas letras, testados antes dos de uma na tokenização.
SUFIXOS_COMPOSTOS = ("do", "od", "qm")

# Notações de horizonte mesclado previstas (1996, p. 49). `Bw/C/R` é ternário —
# um parser que assuma dois componentes falha nele.
MESCLADOS_PREVISTOS = frozenset({
    "E/Bh", "Bh/E", "Bs/E", "E/Bs", "Bt/A", "Bw/C/R",
    "Cr/A", "A/Cr", "Cr/B", "B/Cr",
})

_RE_SIMBOLO = re.compile(
    r"^(?P<litologico>[2-9])?"
    r"(?P<principal>[A-Z]{1,2})"
    r"(?P<sufixos>[^\d'\"’”]*)"
    r"(?P<indice>\d+)?"
    r"(?P<repeticao>['\"’”]*)$"
)


# ---------------------------------------------------------------------------
# Notação legada — mapas NORMATIVOS (Larach et al., 1988, Anexo 1)
#
# O BDSolos agrega campanhas de décadas diferentes e ~14% dos horizontes usam a
# convenção anterior. Não são símbolos malformados — são de outra convenção.
#
# 🚨 Estes mapas vêm da norma, não de inferência. A primeira versão deste módulo
# tratava o dígito de `B2t` como índice de profundidade e "modernizava" para
# `Bt2`. **Está errado**: na convenção SNLCS 1962, `B2` é a designação do
# próprio horizonte B, e `B1`/`B3` são horizontes distintos (transicionais).
# ---------------------------------------------------------------------------

# Horizontes principais: SNLCS 1962 → SNLCS 1986 (Anexo 1, p. 33).
MAPA_PRINCIPAIS_1962: dict[str, tuple[str, ...]] = {
    "O1": ("Oo",),
    "O2": ("Od", "Odo"),
    "A1": ("A",),
    "A2": ("E",),
    "A3": ("AB", "EB"),
    "B1": ("BA", "BE"),
    "B2": ("B",),
    "B3": ("BC",),
    "C1": ("CB",),
    "C2": ("C",),
    "R": ("R",),
}

# Sufixos: notação anterior → atual (Anexo 1, p. 35).
MAPA_SUFIXOS_ANTERIORES: dict[str, str] = {
    "cm": "c",
    "pl": "f",
    "ca": K_BARRA,   # ⭐ o `k̄` tinha notação própria antes: `ca`
    "si": "q",
    "ir": "s",
    "cs": "y",
    "sa": "z",
}

_RE_SUFIXO_ANTERIOR = re.compile(
    r"^(?P<prefixo>[2-9]|I{1,3}|IV|VI{0,3}|V)?"
    r"(?P<principal>[A-Z]{1,3})"
    r"(?P<sufixo>" + "|".join(MAPA_SUFIXOS_ANTERIORES) + r")"
    r"(?P<indice>\d*)$")

_RE_PRINCIPAL_1962 = re.compile(
    r"^(?P<prefixo>[2-9]|I{1,3}|IV|VI{0,3}|V)?"
    r"(?P<designacao>[OABC][123])"
    r"(?P<resto>\d*[a-z]*)$")

_RE_LEGADO_ROMANO = re.compile(r"^(?P<romano>I{2,3}|IV|VI{0,3}|V)(?P<resto>[A-Z].*)$")

#: Numeral romano **transcrito com o dígito 1**. 🚨 Achado em
#: `GeoTab_RN_021_Ceara_Mirim` (2026-09-17), que registra `11C1g` e `111C2` —
#: são `IIC1g` e `IIIC2`, e o `I` virou `1` em alguma etapa de transcrição.
#: Aceita-se só a corrida de **dois ou três** `1` seguida de letra maiúscula:
#: o prefixo de descontinuidade litológica da notação atual é um dígito só,
#: então `11` e `111` não têm leitura moderna possível e a tradução é unívoca.
#: ⚠️ Um `1` isolado fica de fora de propósito — `1C` seria adivinhação, e a
#: norma não marca o primeiro material litológico com prefixo nenhum.
_RE_ROMANO_TRANSCRITO = re.compile(r"^(?P<uns>1{2,3})(?P<resto>[A-Z].*)$")
_RE_LEGADO_PARENTESE = re.compile(r"^\((?P<principal>[A-Z])\)(?P<indice>\d*)$")

_ROMANOS = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


def moderniza(simbolo: str) -> str | None:
    """Traduz notação legada para a atual — **só quando a norma é unívoca**.

    Devolve None quando a tradução seria adivinhação, e isso é o comportamento
    correto: a convenção usada num registro **não vem marcada no dado**, e vários
    símbolos antigos mapeiam para mais de um símbolo atual (`A3` → `AB` ou `EB`,
    conforme haja ou não `E` acima). Ver `leituras()` para as alternativas.

    Nunca reescreve o dado. A norma manda confirmar o nome do horizonte contra
    os dados analíticos, e essa decisão é do curador.
    """
    candidatos = leituras(simbolo)
    return candidatos[0] if len(candidatos) == 1 else None


def leituras(simbolo: str) -> list[str]:
    """Todas as leituras atuais possíveis de um símbolo legado. [] se não for."""
    bruto = normaliza(simbolo)

    achado = _RE_LEGADO_PARENTESE.match(bruto)
    if achado:
        # `(B)` era o B incipiente entre parênteses.
        return ["Bi" + (achado.group("indice") or "")]

    achado = _RE_ROMANO_TRANSCRITO.match(bruto)
    if achado:
        # Reescreve o dígito no numeral que ele representa e reentra: daí para
        # frente é o caminho normal do romano legado.
        romano = "I" * len(achado.group("uns"))
        return leituras(romano + achado.group("resto"))

    achado = _RE_LEGADO_ROMANO.match(bruto)
    if achado:
        arabico = _ROMANOS.get(achado.group("romano"))
        if not arabico:
            return []
        internas = leituras(achado.group("resto")) or [achado.group("resto")]
        return [f"{arabico}{x}" for x in internas]

    achado = _RE_SUFIXO_ANTERIOR.match(bruto)
    if achado:
        atual = MAPA_SUFIXOS_ANTERIORES[achado.group("sufixo")]
        return ["".join([achado.group("prefixo") or "",
                         achado.group("principal"), atual,
                         achado.group("indice") or ""])]

    achado = _RE_PRINCIPAL_1962.match(bruto)
    if achado:
        alvos = MAPA_PRINCIPAIS_1962.get(achado.group("designacao"))
        resto = achado.group("resto") or ""
        # ⚠️ `A2`, `B2`, `C1` sozinhos são AMBÍGUOS: tanto designação de 1962
        # quanto horizonte moderno com índice de profundidade — e a convenção
        # não vem marcada no dado. Só há evidência de notação antiga quando um
        # sufixo aparece DEPOIS do dígito (`B2t`), porque a convenção atual põe
        # o índice sempre no fim (`Bt2`). Sem essa evidência, não se afirma.
        if not alvos or not any(ch.isalpha() for ch in resto):
            return []
        prefixo = achado.group("prefixo") or ""
        # `B21t` = subdivisão 1 do B2, com sufixo t → `Bt1`.
        indice, sufixos = "", ""
        for ch in resto:
            (sufixos, indice) = (sufixos + ch, indice) if ch.isalpha() else (sufixos, indice + ch)
        return [f"{prefixo}{alvo}{sufixos}{indice}" for alvo in alvos]

    return []


def _e_legado(bruto: str) -> bool:
    return bool(leituras(bruto))


@dataclass(frozen=True)
class Achado:
    """Uma observação sobre um símbolo. Sinaliza; nunca decide exclusão."""

    codigo: str
    gravidade: str  # "erro" | "alerta" | "suspeita"
    mensagem: str


@dataclass
class Simbolo:
    """Decomposição de um símbolo de horizonte."""

    bruto: str
    litologico: int | None = None
    principal: str = ""
    sufixos: list[str] = field(default_factory=list)
    indice: int | None = None
    repeticao: int = 0
    transicional: bool = False
    mesclado: bool = False
    componentes: list[str] = field(default_factory=list)
    reconhecido: bool = True


def normaliza(simbolo: str) -> str:
    """NFC, sem espaços nas bordas. Preserva o mácron de `k̄`.

    NFC compõe o que der; `k` + U+0304 não tem forma pré-composta em Unicode,
    então sobrevive como sequência de dois pontos de código — que é justamente
    o motivo de qualquer passo `encode("ascii")` destruí-lo.
    """
    return unicodedata.normalize("NFC", (simbolo or "").strip())


def _tokeniza_sufixos(texto: str) -> list[str]:
    """Quebra a parte minúscula em sufixos, com mácron colado à letra."""
    tokens: list[str] = []
    i = 0
    while i < len(texto):
        # Um mácron combinante pertence ao caractere anterior.
        if i + 1 < len(texto) and texto[i + 1] == MACRON:
            tokens.append(texto[i:i + 2])
            i += 2
            continue
        for composto in SUFIXOS_COMPOSTOS:
            if texto.startswith(composto, i):
                tokens.append(composto)
                i += len(composto)
                break
        else:
            tokens.append(texto[i])
            i += 1
    return tokens


def analisa(simbolo: str) -> Simbolo:
    """Decompõe o símbolo. Não julga — `valida()` julga."""
    bruto = normaliza(simbolo)
    if "/" in bruto:
        return Simbolo(bruto=bruto, mesclado=True,
                       componentes=[p for p in bruto.split("/") if p])

    achado = _RE_SIMBOLO.match(bruto)
    if not achado:
        return Simbolo(bruto=bruto, reconhecido=False)

    litologico = achado.group("litologico")
    indice = achado.group("indice")
    return Simbolo(
        bruto=bruto,
        litologico=int(litologico) if litologico else None,
        principal=achado.group("principal"),
        transicional=len(achado.group("principal")) == 2,
        sufixos=_tokeniza_sufixos(achado.group("sufixos") or ""),
        indice=int(indice) if indice else None,
        repeticao=len(achado.group("repeticao") or ""),
    )


def valida(simbolo: str, edicao: str = EDICAO_PADRAO) -> list[Achado]:
    """Confere um símbolo contra a gramática. Devolve os achados, sem exceção.

    Lista vazia significa "nada a apontar sob esta edição" — não significa que
    o símbolo esteja confirmado contra os dados analíticos, que é exigência
    separada da norma. A 7ª edição é mais enfática que a 3ª: onde 1996 falava
    em "confirmação dos nomes", 2015 (p. 53) fala em **"correção ou
    confirmação"** dos nomes e de seus sufixos, de posse dos resultados
    analíticos — a norma admite explicitamente que o símbolo anotado em campo
    pode estar errado e deva ser corrigido antes de classificar.
    """
    tabela = APLICABILIDADE[edicao]
    s = analisa(simbolo)
    achados: list[Achado] = []

    if not s.bruto:
        return [Achado("VAZIO", "erro", "símbolo ausente")]

    # Notação legada é outra convenção, não malformação — classificar como erro
    # soterraria os achados reais. Ver o bloco de notação legada acima.
    candidatos = leituras(s.bruto)
    if candidatos:
        if len(candidatos) == 1:
            detalhe = f"equivale a {candidatos[0]!r} na convenção atual"
            gravidade = "nota"
        else:
            detalhe = ("admite mais de uma leitura atual ("
                       + ", ".join(repr(x) for x in candidatos)
                       + ") — a norma não desambigua sem o perfil completo")
            gravidade = "alerta"
        achados = [Achado("NOTACAO_LEGADA", gravidade,
                          f"{s.bruto!r} usa notação anterior; {detalhe}")]
        if _RE_ROMANO_TRANSCRITO.match(normaliza(s.bruto)):
            # Não é só notação antiga: é notação antiga **corrompida na
            # transcrição**. O prefixo litológico era um numeral romano e
            # chegou como dígito, de modo que o símbolo deixou de casar com
            # qualquer forma — nem a antiga, nem a atual.
            achados.append(Achado(
                "ROMANO_TRANSCRITO", "alerta",
                f"{s.bruto!r} traz o prefixo litológico como repetição do "
                "dígito 1, e não como numeral romano — 'I' virou '1' na "
                "transcrição. É perda de informação na origem, do mesmo tipo "
                "do mácron e do itálico: o dado chega válido à vista e "
                "inanalisável pela forma"))
        return achados

    if s.mesclado:
        if s.bruto not in MESCLADOS_PREVISTOS:
            achados.append(Achado(
                "MESCLADO_NAO_LISTADO", "nota",
                f"{s.bruto!r} não está entre os mesclados exemplificados pela "
                "norma; a lista é ilustrativa, então isto só vira problema se "
                "algum componente for inválido"))
        for parte in s.componentes:
            achados.extend(a for a in valida(parte, edicao)
                           if a.codigo != "SEM_SUFIXO")
        return achados

    if not s.reconhecido:
        return [Achado("NAO_ANALISAVEL", "erro",
                       f"{s.bruto!r} não casa com a forma "
                       "[prefixo][MAIÚSCULA][sufixos][índice][apóstrofos]")]

    if s.transicional:
        if s.principal not in TRANSICIONAIS:
            achados.append(Achado(
                "TRANSICIONAL_NAO_PREVISTO", "alerta",
                f"{s.principal!r} não consta dos horizontes transicionais "
                "da norma"))
            return achados
    elif s.principal not in PRINCIPAIS:
        achados.append(Achado(
            "PRINCIPAL_DESCONHECIDO", "erro",
            f"{s.principal!r} não é horizonte ou camada principal "
            f"({', '.join(PRINCIPAIS)})"))
        return achados

    # Num transicional o horizonte tem características dos dois componentes,
    # então a aplicabilidade é a **união** dos dois conjuntos: `BCr` é legítimo
    # porque `r` pertence a `C`, e `ABt` porque `t` pertence a `B`. Usar só o
    # dominante rejeitaria notações corretas.
    #
    # ✅ Isto era inferência minha e passou a ter respaldo normativo: a 7ª
    # edição (p. 53) acrescenta a regra explícita de que "as notações de sufixos
    # podem ser aplicadas a horizontes transicionais que apresentem atributos
    # que expressem pedogênese", com os exemplos `BAw` e `BCf`.
    admitidos: frozenset[str] = frozenset()
    for letra in s.principal:
        admitidos |= tabela.get(letra, frozenset())
    referencia = s.principal

    for sufixo in s.sufixos:
        if sufixo.isupper() or (sufixo and sufixo[0].isupper()):
            gravidade, extra = "erro", ""
            if sufixo.lower().startswith("k"):
                gravidade = "suspeita"
                extra = (" — maiúscula em sufixo de carbonato é candidata a "
                         "traço de `k̄` perdido na transcrição")
            achados.append(Achado(
                "SUFIXO_MAIUSCULO", gravidade,
                f"sufixo {sufixo!r} em maiúscula; a norma exige "
                f"minúsculas{extra}"))
            continue
        if sufixo not in SUFIXOS:
            achados.append(Achado(
                "SUFIXO_DESCONHECIDO", "erro",
                f"{sufixo!r} não é sufixo da norma"))
            continue
        if sufixo not in admitidos:
            achados.append(Achado(
                "SUFIXO_NAO_APLICAVEL", "alerta",
                f"sufixo {sufixo!r} não previsto para o horizonte "
                f"{referencia!r} na edição {edicao}"))

    # `b` deve vir precedido de outro sufixo em notação binária: Btb, não Bb.
    if s.sufixos and s.sufixos[0] == "b":
        achados.append(Achado(
            "B_SEM_PRECEDENTE", "alerta",
            "sufixo 'b' (enterrado) deve ser precedido de outro sufixo "
            "em notação binária, como 'Btb'"))

    # Precedência: d, i, o, h, s, t, u, r, w vêm antes dos demais.
    posicoes = [PRECEDENCIA.index(x) if x in PRECEDENCIA else None
                for x in s.sufixos]
    for anterior, atual in zip(posicoes, posicoes[1:]):
        if anterior is None and atual is not None:
            achados.append(Achado(
                "PRECEDENCIA", "alerta",
                f"ordem dos sufixos {''.join(s.sufixos)!r} contraria a "
                f"precedência {', '.join(PRECEDENCIA)}"))
            break

    # ⚠️ Divergência norma × prática, não malformação. A norma pede sufixo
    # para todos os principais exceto R e, às vezes, C e E — mas `A1`/`A2` sem
    # sufixo é uso corrente e responde por ~15% do PYKKA7. Fica em "nota" para
    # não soterrar os achados que exigem revisão.
    exige_sufixo = not s.transicional and s.principal not in ("R", "C", "E")
    if exige_sufixo and not s.sufixos:
        achados.append(Achado(
            "SEM_SUFIXO", "nota",
            f"horizonte {s.principal!r} sem sufixo; a norma pede sufixo para "
            "todos os principais exceto R e, às vezes, C e E"))

    if s.principal == "R" and s.sufixos:
        achados.append(Achado(
            "R_COM_SUFIXO", "erro",
            "camada R não recebe sufixo"))

    if s.repeticao > 2:
        achados.append(Achado(
            "REPETICAO_EXCESSIVA", "alerta",
            "a norma prevê apóstrofo simples (2ª ocorrência) e duplo (3ª)"))

    return achados


def suspeita_k_barra_perdido(
    simbolo: str,
    caco3_equivalente: float | None,
    caco3_subjacente: float | None = None,
) -> Achado | None:
    """Detecta `k` que provavelmente era `k̄` antes da transcrição.

    É a única defesa depois que o dado chega: nenhuma verificação de
    completude, unicidade ou faixa pega esta perda — o valor está presente e
    bem-formado. Só coerência entre campos denuncia.

    Devolve None quando não há suspeita. Nunca reescreve o símbolo: a decisão
    é do curador.
    """
    s = analisa(simbolo)
    if s.mesclado or not s.reconhecido:
        return None

    tem_k_simples = any(x.lower() == "k" for x in s.sufixos)
    if not tem_k_simples or caco3_equivalente is None:
        return None
    if caco3_equivalente < LIMIAR_CACO3:
        return None

    if caco3_subjacente is not None:
        if caco3_equivalente - caco3_subjacente < DELTA_CACO3:
            return None
        detalhe = (f"{caco3_equivalente:.0f} g·kg⁻¹, "
                   f"{caco3_equivalente - caco3_subjacente:.0f} acima do "
                   "horizonte subjacente")
    else:
        detalhe = (f"{caco3_equivalente:.0f} g·kg⁻¹; segundo critério "
                   "(≥ 50 acima do subjacente) não verificado")

    return Achado(
        "K_BARRA_CANDIDATO", "suspeita",
        f"{s.bruto!r} tem sufixo 'k' e CaCO₃ equivalente de {detalhe} — "
        f"satisfaz o limiar de `k̄` (≥ {LIMIAR_CACO3:.0f} g·kg⁻¹). "
        "Candidato a mácron perdido na transcrição.")


def resume(achados: list[Achado]) -> str:
    """Uma linha por achado, para log de task."""
    return "; ".join(f"[{a.gravidade}:{a.codigo}] {a.mensagem}"
                     for a in achados) or "sem achados"
