"""2º e 3º níveis categóricos das cinco ordens do recorte — SiBCS 5ª ed. (2018).

Decisão de 2026-10-12 ("saída C"): formalizar Latossolos, Argissolos,
Luvissolos, Espodossolos e Cambissolos até o 4º nível; se não couber no
prazo, reportar o Acerto@k até o nível pronto e declarar na §3.5. Este módulo
cobre **2º e 3º níveis**; o 4º (448 subgrupos) está em `niveis5_subgrupos.py`.

Cada classe é uma `Regra`, como no 1º nível: a base é dado, e o avaliador é
o mesmo. A precedência dentro de cada nível é a ordem do texto da norma, e
a primeira regra satisfeita conclui. O texto de cada condição foi lido no
PDF da 5ª edição em 2026-10-15; as páginas são as **impressas**.

Leituras declaradas (⚠️), todas registradas na fonte da condição:

* "horizonte B (inclusive BA)" é `principal B` — inclui o BC, que a 5ª
  edição não exclui nos 2º e 3º níveis destas ordens (exceto no caráter
  crômico e no solum dos pálicos, que o excluem por texto);
* "X e Y, ambas na maior parte" é a conjunção de "X na maior parte" e "Y na
  maior parte" — a norma não diz se o mesmo horizonte deve ter os dois;
* "Outros solos com saturação por bases < 50%" mantém a condição: o texto a
  enuncia, e um Latossolo Bruno eutrófico fica sem grande grupo (a 5ª não
  prevê Latossolos Brunos Eutróficos) em vez de ser forçado num.
"""

from __future__ import annotations

import unicodedata

from . import horizontes
from .avaliador import Resultado, classificar
from .predicados_niveis import PREDICADOS_NIVEIS
from .regras import (Booleano, Compara, Derivado, E, Existe, Ou, Pendente,
                     Regra, Residual, Seletor)

horizontes.PREDICADOS.update(PREDICADOS_NIVEIS)


def _p(pagina: str) -> str:
    return f"SiBCS 5ª ed. (2018), p. {pagina}"


B100 = Seletor(principal="B", seccao_controle_cm=100)
ATE_150 = Seletor(inicio_ate_cm=150)
ATE_100 = Seletor(inicio_ate_cm=100)


def mp(atributo, operador, limiar, fonte, unidade=""):
    """\"… na maior parte dos primeiros 100 cm do horizonte B (inclusive BA)\"."""
    return Compara(atributo=atributo, operador=operador, limiar=limiar,
                   onde=B100, agregacao="maior parte", unidade=unidade,
                   fonte=fonte)


def algum(atributo, operador, limiar, onde, fonte, unidade=""):
    """\"… em um ou mais horizontes dentro de N cm\"."""
    return Compara(atributo=atributo, operador=operador, limiar=limiar,
                   onde=onde, agregacao="qualquer", unidade=unidade, fonte=fonte)


def v_baixa(f): return mp("V_PERCENT", "<", 50, f, "%")
def v_alta(f): return mp("V_PERCENT", ">=", 50, f, "%")
def aluminico(f): return mp("ALUMINICO", ">=", 1, f)
def ta(f): return mp("ATIVIDADE_ARGILA", ">=", 27, f, "cmolc/kg de argila")
def tb(f): return mp("ATIVIDADE_ARGILA", "<", 27, f, "cmolc/kg de argila")
def ferrico(f): return E(partes=(mp("TEOR_FE", ">=", 180, f, "g/kg"),
                                 mp("TEOR_FE", "<", 360, f, "g/kg")))
def perferrico(f): return mp("TEOR_FE", ">=", 360, f, "g/kg")
def acrico_150(f): return algum("ACRICO", ">=", 1, ATE_150, f)
def coeso_150(f): return Booleano(atributo="COESO", onde=ATE_150, fonte=f)
def carbonatico(onde, f): return algum("EQUI_CACO3", ">=", 150, onde, f, "g/kg")
def sodico_150(f): return algum("SAT_NA", ">=", 15, ATE_150, f, "%")
def salico_150(f): return algum("COND_ELETR", ">=", 7, ATE_150, f, "dS/m")


def _cor_mp(atributo, f):
    return mp(atributo, ">=", 1, f)


# ============================================================ 2º nível ======

SUBORDENS: dict[str, tuple[Regra, ...]] = {
    "LATOSSOLO": (
        Regra("BRUNO", E(partes=(
            Booleano(atributo="RETRATIL", fonte=_p("195") + " — caráter retrátil"),
            Ou(partes=(Derivado(predicado="horizonte A húmico", fonte=_p("195")),
                       Derivado(predicado="carbono orgânico > 10 g/kg até 70 cm",
                                fonte=_p("195")))),
            Derivado(predicado="cor brunada na parte superior do B (Latossolos Brunos)",
                     fonte=_p("195")),
        )), fonte=_p("195")),
        Regra("AMARELO", mp("MATIZ_NUM", ">=", 17.5, _p("195") + " — matiz 7,5YR ou mais amarelo")),
        Regra("VERMELHO", mp("MATIZ_NUM", "<=", 12.5, _p("195") + " — matiz 2,5YR ou mais vermelho")),
        Regra("VERMELHO-AMARELO", Residual(fonte=_p("196"))),
    ),
    "ARGISSOLO": (
        Regra("BRUNO-ACINZENTADO", E(partes=(
            _cor_mp("COR_BRUNO_ACINZENTADA", _p("115") + " — matiz ≥ 5YR, valor 3 a 4, croma ≤ 4"),
            Pendente(motivo="escurecimento expressivo da porção superior do B "
                            "(comparação de cores úmidas e secas entre sub-horizontes)",
                     fonte=_p("115")),
        )), fonte=_p("115")),
        Regra("ACINZENTADO", _cor_mp("COR_ACINZENTADA", _p("116") + " — matiz ≥ 7,5YR, valor ≥ 5, croma < 4")),
        Regra("AMARELO", mp("MATIZ_NUM", ">=", 17.5, _p("116") + " — matiz 7,5YR ou mais amarelo")),
        Regra("VERMELHO", mp("MATIZ_NUM", "<=", 12.5, _p("116") + " — matiz 2,5YR ou mais vermelho")),
        Regra("VERMELHO-AMARELO", Residual(fonte=_p("116"))),
    ),
    "LUVISSOLO": (
        Regra("CRÔMICO", Compara(atributo="CROMICO", operador=">=", limiar=1,
                                 onde=B100, agregacao="maior parte",
                                 fonte=_p("213") + " — caráter crômico (p. 34); "
                                       "⚠️ o BC, que o caráter exclui, entra na seleção")),
        Regra("HÁPLICO", Residual(fonte=_p("213"))),
    ),
    "ESPODOSSOLO": (
        Regra("HUMILÚVICO", Derivado(predicado="B espódico com Bh/Bhm", fonte=_p("165"))),
        Regra("FERRILÚVICO", Derivado(predicado="B espódico com Bs/Bsm", fonte=_p("165"))),
        Regra("FERRI-HUMILÚVICO", Residual(fonte=_p("165"))),
    ),
    "CAMBISSOLO": (
        # Existe(principal O) primeiro: sem horizonte O, a comparação não
        # selecionaria nada e devolveria indeterminado, quando a ausência
        # observada do O refuta a subordem (corrigido em 2026-10-15).
        Regra("HÍSTICO", E(partes=(
            Existe(onde=Seletor(principal="O"), fonte=_p("139") + " — horizonte O"),
            Compara(atributo="C_ORG", operador=">=", limiar=80,
                    onde=Seletor(principal="O"), agregacao="qualquer",
                    unidade="g/kg",
                    fonte=_p("139") + " — horizonte O hístico (p. 49: C ≥ 80 g/kg); "
                          "a espessura de Organossolo já foi excluída no 1º nível"),
        ))),
        Regra("HÚMICO", Derivado(predicado="horizonte A húmico", fonte=_p("139"))),
        Regra("FLÚVICO", Booleano(atributo="FLUVICO", onde=ATE_150, fonte=_p("139"))),
        Regra("HÁPLICO", Residual(fonte=_p("139"))),
    ),
}


# ============================================================ 3º nível ======

def _espodicos(pagina):
    """Os quatro grandes grupos de cada subordem dos Espodossolos, p. 166-168."""
    def hidro(com_mosq):
        return Derivado(predicado=("H hístico, Eg ou mosqueado até 100 cm" if com_mosq
                                   else "H hístico ou Eg até 100 cm"), fonte=_p(pagina))
    def regras(com_mosq):
        return (
            Regra("Hidro-hiperespessos", E(partes=(
                Derivado(predicado="B espódico entre 200 e 400 cm", fonte=_p(pagina)),
                Derivado(predicado="saturado com água (mal ou muito mal drenado)", fonte=_p(pagina)),
                hidro(com_mosq)))),
            Regra("Hidromórfico", E(partes=(
                Derivado(predicado="B espódico até 200 cm", fonte=_p(pagina)),
                Derivado(predicado="saturado com água (mal ou muito mal drenado)", fonte=_p(pagina)),
                hidro(com_mosq)))),
            Regra("Hiperespesso", Derivado(predicado="B espódico entre 200 e 400 cm", fonte=_p(pagina))),
            Regra("Órtico", Residual(fonte=_p(pagina))),
        )
    return regras


GRANDES_GRUPOS: dict[tuple[str, str], tuple[Regra, ...]] = {
    # ---------------------------------------------------------- Latossolos --
    ("LATOSSOLO", "BRUNO"): (
        Regra("Aluminoférrico", E(partes=(aluminico(_p("196")), ferrico(_p("196"))))),
        Regra("Alumínico", aluminico(_p("196"))),
        Regra("Distroférrico", E(partes=(v_baixa(_p("196")), ferrico(_p("196"))))),
        Regra("Distrófico", v_baixa(_p("196"))),
    ),
    ("LATOSSOLO", "AMARELO"): (
        Regra("Acriférrico", E(partes=(acrico_150(_p("196")), ferrico(_p("196"))))),
        Regra("Ácrico", acrico_150(_p("196"))),
        Regra("Alumínico", aluminico(_p("197"))),
        Regra("Distroférrico", E(partes=(v_baixa(_p("197")), ferrico(_p("197"))))),
        Regra("Distrocoeso", E(partes=(v_baixa(_p("197")), coeso_150(_p("197"))))),
        Regra("Distrófico", v_baixa(_p("197"))),
        Regra("Eutrófico", v_alta(_p("197"))),
    ),
    ("LATOSSOLO", "VERMELHO"): (
        Regra("Perférrico", perferrico(_p("197"))),
        Regra("Acriférrico", E(partes=(acrico_150(_p("197")), ferrico(_p("197"))))),
        Regra("Ácrico", acrico_150(_p("197"))),
        Regra("Aluminoférrico", E(partes=(aluminico(_p("198")), ferrico(_p("198"))))),
        Regra("Distroférrico", E(partes=(v_baixa(_p("198")), ferrico(_p("198"))))),
        Regra("Distrófico", v_baixa(_p("198"))),
        Regra("Eutroférrico", E(partes=(v_alta(_p("198")), ferrico(_p("198"))))),
        Regra("Eutrófico", v_alta(_p("198"))),
    ),
    ("LATOSSOLO", "VERMELHO-AMARELO"): (
        Regra("Acriférrico", E(partes=(acrico_150(_p("198")), ferrico(_p("198"))))),
        Regra("Ácrico", acrico_150(_p("198"))),
        Regra("Alumínico", aluminico(_p("199"))),
        Regra("Distroférrico", E(partes=(v_baixa(_p("199")), ferrico(_p("199"))))),
        Regra("Distrófico", v_baixa(_p("199"))),
        Regra("Eutrófico", v_alta(_p("199"))),
    ),
    # ---------------------------------------------------------- Argissolos --
    ("ARGISSOLO", "BRUNO-ACINZENTADO"): (
        Regra("Ta Alumínico", E(partes=(ta(_p("116")), aluminico(_p("116"))))),
        Regra("Alumínico", aluminico(_p("116"))),
        Regra("Distrófico", v_baixa(_p("116"))),
    ),
    ("ARGISSOLO", "ACINZENTADO"): (
        Regra("Distrocoeso", E(partes=(v_baixa(_p("117")), coeso_150(_p("117"))))),
        Regra("Distrófico", v_baixa(_p("117"))),
        Regra("Eutrófico", v_alta(_p("117"))),
    ),
    ("ARGISSOLO", "AMARELO"): (
        Regra("Ta Alumínico", E(partes=(ta(_p("117")), aluminico(_p("117"))))),
        Regra("Alumínico", aluminico(_p("117"))),
        Regra("Distrocoeso", E(partes=(v_baixa(_p("117")), coeso_150(_p("117"))))),
        Regra("Distrófico", v_baixa(_p("117"))),
        Regra("Eutrocoeso", E(partes=(v_alta(_p("117")), coeso_150(_p("117"))))),
        Regra("Eutrófico", v_alta(_p("118"))),
    ),
    ("ARGISSOLO", "VERMELHO"): (
        Regra("Ta Alumínico", E(partes=(ta(_p("118")), aluminico(_p("118"))))),
        Regra("Alumínico", aluminico(_p("118"))),
        Regra("Ta Distrófico", E(partes=(ta(_p("118")), v_baixa(_p("118"))))),
        Regra("Distrófico", v_baixa(_p("118"))),
        Regra("Eutroférrico", E(partes=(v_alta(_p("118")), ferrico(_p("118"))))),
        Regra("Eutrófico", v_alta(_p("118"))),
    ),
    ("ARGISSOLO", "VERMELHO-AMARELO"): (
        Regra("Ta Alumínico", E(partes=(ta(_p("118")), aluminico(_p("118"))))),
        Regra("Alumínico", aluminico(_p("119"))),
        Regra("Ta Distrófico", E(partes=(ta(_p("119")), v_baixa(_p("119"))))),
        Regra("Distrófico", v_baixa(_p("119"))),
        Regra("Eutrófico", v_alta(_p("119"))),
    ),
    # ---------------------------------------------------------- Luvissolos --
    ("LUVISSOLO", "CRÔMICO"): (
        Regra("Carbonático", carbonatico(ATE_100, _p("213") + " — caráter carbonático "
                                         "ou horizonte cálcico (ambos ≥ 150 g/kg de CaCO3, p. 33 e 71)")),
        Regra("Pálico", Derivado(predicado="solum (A + B, inclusive E, exclusive BC) > 80 cm",
                                 fonte=_p("214"))),
        Regra("Órtico", Residual(fonte=_p("214"))),
    ),
    ("LUVISSOLO", "HÁPLICO"): (
        Regra("Pálico", Derivado(predicado="solum (A + B, inclusive E, exclusive BC) > 80 cm",
                                 fonte=_p("214"))),
        Regra("Órtico", Residual(fonte=_p("214"))),
    ),
    # -------------------------------------------------------- Espodossolos --
    ("ESPODOSSOLO", "HUMILÚVICO"): _espodicos("166")(com_mosq=False),
    ("ESPODOSSOLO", "FERRILÚVICO"): _espodicos("167")(com_mosq=True),
    ("ESPODOSSOLO", "FERRI-HUMILÚVICO"): _espodicos("168")(com_mosq=True),
    # --------------------------------------------------------- Cambissolos --
    ("CAMBISSOLO", "HÍSTICO"): (
        Regra("Alumínico", aluminico(_p("140"))),
        Regra("Distrófico", v_baixa(_p("140"))),
    ),
    ("CAMBISSOLO", "HÚMICO"): (
        Regra("Aluminoférrico", E(partes=(aluminico(_p("140")), ferrico(_p("140"))))),
        Regra("Alumínico", aluminico(_p("140"))),
        Regra("Distroférrico", E(partes=(v_baixa(_p("140")), ferrico(_p("140"))))),
        Regra("Distrófico", v_baixa(_p("140"))),
    ),
    ("CAMBISSOLO", "FLÚVICO"): (
        Regra("Carbonático", carbonatico(ATE_150, _p("140"))),
        Regra("Sódico", sodico_150(_p("141"))),
        Regra("Sálico", salico_150(_p("141"))),
        Regra("Alumínico", aluminico(_p("141"))),
        Regra("Ta Distrófico", E(partes=(ta(_p("141")), v_baixa(_p("141"))))),
        Regra("Ta Eutrófico", E(partes=(ta(_p("141")), v_alta(_p("141"))))),
        Regra("Tb Distrófico", E(partes=(tb(_p("141")), v_baixa(_p("141"))))),
        Regra("Tb Eutrófico", E(partes=(tb(_p("141")), v_alta(_p("141"))))),
    ),
    ("CAMBISSOLO", "HÁPLICO"): (
        Regra("Carbonático", carbonatico(ATE_150, _p("141"))),
        Regra("Sódico", sodico_150(_p("142"))),
        Regra("Perférrico", perferrico(_p("142"))),
        Regra("Ta Alumínico", E(partes=(ta(_p("142")), aluminico(_p("142"))))),
        Regra("Ta Distrófico", E(partes=(ta(_p("142")), v_baixa(_p("142"))))),
        Regra("Ta Eutroférrico", E(partes=(ta(_p("142")), v_alta(_p("142")), ferrico(_p("142"))))),
        Regra("Ta Eutrófico", E(partes=(ta(_p("142")), v_alta(_p("142"))))),
        Regra("Tb Alumínico", E(partes=(tb(_p("142")), aluminico(_p("142"))))),
        Regra("Tb Distroférrico", E(partes=(tb(_p("142")), v_baixa(_p("142")), ferrico(_p("142"))))),
        Regra("Tb Distrófico", E(partes=(tb(_p("143")), v_baixa(_p("143"))))),
        Regra("Tb Eutroférrico", E(partes=(tb(_p("143")), v_alta(_p("143")), ferrico(_p("143"))))),
        Regra("Tb Eutrófico", E(partes=(tb(_p("143")), v_alta(_p("143"))))),
    ),
}


# ======================================================= classificação ======

def normaliza(nome) -> str:
    """Para comparar rótulos: sem acento, maiúsculas, sem hífen, sem 's' final.

    O hífen sai porque o BDSolos grafa `FERRIHUMILÚVICO` onde a norma escreve
    `FERRI-HUMILÚVICO`; diferença de grafia não é diferença de classe.
    """
    if not nome:
        return ""
    t = "".join(c for c in unicodedata.normalize("NFD", str(nome))
                if unicodedata.category(c) != "Mn").upper().replace("-", "")
    return " ".join(p[:-1] if p.endswith("S") and len(p) > 3 else p for p in t.split())


def coincide(esperado, obtido) -> bool:
    """O rótulo registrado designa a classe obtida?

    Aceita o rótulo com o nome dos níveis de cima ("LUVISSOLO HÁPLICO Órtico"
    no campo do grande grupo, como vem em alguns registros do BDSolos).
    """
    e, o = normaliza(esperado), normaliza(obtido)
    return bool(o) and (e == o or e.endswith(" " + o))


def classificar_niveis(perfil, chave=None) -> list[Resultado | None]:
    """Resultados do 1º ao 4º nível; None onde o nível de cima não conclui.

    Só se desce de nível quando o de cima é **conclusivo**: classificar a
    subordem de uma ordem apenas alcançável seria afirmar o que a norma ainda
    não decidiu. O 4º nível vem de `niveis5_subgrupos`.
    """
    from .niveis5_subgrupos import SUBGRUPOS
    r1 = classificar(perfil, chave)
    saida: list[Resultado | None] = [r1, None, None, None]
    if not r1.conclusivo or r1.classe not in SUBORDENS:
        return saida
    r2 = classificar(perfil, SUBORDENS[r1.classe])
    saida[1] = r2
    if not r2.conclusivo or (r1.classe, r2.classe) not in GRANDES_GRUPOS:
        return saida
    r3 = classificar(perfil, GRANDES_GRUPOS[(r1.classe, r2.classe)])
    saida[2] = r3
    chave4 = (r1.classe, r2.classe, r3.classe)
    if not r3.conclusivo or chave4 not in SUBGRUPOS:
        return saida
    saida[3] = classificar(perfil, SUBGRUPOS[chave4])
    return saida
