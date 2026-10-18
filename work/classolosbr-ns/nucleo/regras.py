"""Regras como dados — a decisão de projeto que organiza o núcleo.

Cada condição da norma é um **objeto**, não uma função. O que decide é o
avaliador (`avaliador.py`), que percorre a estrutura. A alternativa rejeitada
foi escrever cada regra como função que também se instrumenta: uma base
povoada de instruções de registro deixa de poder ser lida em paralelo ao texto
do SiBCS, e a legibilidade da base como transcrição da norma é o seu principal
atributo de qualidade (monografia, §4.2.1).

Três consequências decorrem da escolha, sem esforço adicional:

* o mesmo avaliador que registra derivações bem-sucedidas registra as falhas;
* como os limiares são **dados**, a distância entre o valor informado e o
  limiar violado é obtida por leitura do objeto — é a grandeza sobre a qual a
  abdução contrastiva calcula a alteração mínima;
* trocar a lógica bivalente pela de três valores é alteração no avaliador,
  sem tocar em regra alguma.

Toda condição carrega `fonte`: onde, na norma, ela foi lida. Vazio significa
que ninguém conferiu — e o relatório de cobertura reclama.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------- seletores --

@dataclass(frozen=True)
class Seletor:
    """Escolhe horizontes de um perfil.

    `tipo` é um tipo de horizonte diagnóstico (ver `horizontes.py`); `simbolo`
    filtra pela letra principal do símbolo (`"B"`, `"A"`, `"H"`).
    """

    tipo: str | None = None
    principal: str | None = None
    inicio_ate_cm: float | None = None
    primeiro: bool = False
    #: Restringe a ponderação da agregação "maior parte" aos primeiros N cm
    #: contados do **topo do primeiro horizonte selecionado**. É a "seção de
    #: controle" da norma: "na maior parte dos primeiros 100 cm do horizonte
    #: B" não é o mesmo que "na maior parte do horizonte B".
    seccao_controle_cm: float | None = None

    def descricao(self) -> str:
        partes = []
        if self.tipo:
            partes.append(f"horizonte {self.tipo}")
        if self.principal:
            partes.append(f"principal {self.principal}")
        if self.inicio_ate_cm is not None:
            partes.append(f"iniciando até {self.inicio_ate_cm:g} cm")
        if self.seccao_controle_cm is not None:
            partes.append(f"nos primeiros {self.seccao_controle_cm:g} cm")
        return " ".join(partes) or "qualquer horizonte"


# -------------------------------------------------------------- condições ---

@dataclass(frozen=True)
class Condicao:
    """Base — apenas para tipagem. Nenhuma condição sabe se avaliar."""

    fonte: str = ""


@dataclass(frozen=True)
class Existe(Condicao):
    """Existe horizonte que satisfaz o seletor."""

    onde: Seletor = field(default_factory=Seletor)
    imediatamente_abaixo_de: tuple[str, ...] = ()
    fonte: str = ""


@dataclass(frozen=True)
class Compara(Condicao):
    """Compara um atributo contra um limiar, no horizonte selecionado.

    `agregacao` decide o que fazer quando o seletor casa vários horizontes:

    * `"qualquer"` — basta um satisfazer;
    * `"todos"` — todos precisam satisfazer;
    * `"maior parte"` — a **espessura** dos que satisfazem precisa superar a
      metade da espessura total selecionada. É a formulação que a norma usa
      ("na maior parte dos primeiros 100 cm do horizonte B"), e a única que
      reproduz corretamente o empate: metade exata não é maior parte, e a
      norma não diz o que fazer — logo, indeterminado.
    """

    atributo: str = ""
    operador: str = ">="
    limiar: float = 0.0
    onde: Seletor = field(default_factory=Seletor)
    agregacao: str = "qualquer"
    unidade: str = ""
    fonte: str = ""


@dataclass(frozen=True)
class Booleano(Condicao):
    """Um caráter diagnóstico declarado como booleano no contrato."""

    atributo: str = ""
    onde: Seletor = field(default_factory=Seletor)
    esperado: bool = True
    fonte: str = ""


@dataclass(frozen=True)
class E(Condicao):
    partes: tuple = ()
    fonte: str = ""


@dataclass(frozen=True)
class Ou(Condicao):
    partes: tuple = ()
    fonte: str = ""


@dataclass(frozen=True)
class Nao(Condicao):
    parte: Condicao | None = None
    fonte: str = ""


@dataclass(frozen=True)
class Pendente(Condicao):
    """Condição que a norma exige e o dado disponível não expressa.

    Avalia sempre como **indeterminado**. Não é dívida técnica escondida: é a
    forma correta de representar uma exigência que não se pode verificar. O
    efeito é que a classe permanece *alcançável* em vez de ser afirmada ou
    refutada sem base — e o motivo aparece na saída.
    """

    motivo: str = ""
    fonte: str = ""


@dataclass(frozen=True)
class Derivado(Condicao):
    """Predicado composto cuja formulação não cabe em uma comparação.

    Nomeia uma função do registro de `horizontes.py`. A regra continua sendo
    dado — o que ela guarda é o **nome** do predicado, não o código —, e o
    predicado nomeado é auditável em separado, com sua própria citação à
    norma. Usado onde a condição envolve posição relativa, seção de controle
    ou varredura do perfil inteiro.
    """

    predicado: str = ""
    fonte: str = ""


@dataclass(frozen=True)
class Residual(Condicao):
    """\"Outros solos que não se enquadram nas classes anteriores.\"

    Verdadeira por construção quando alcançada: a precedência da chave já
    excluiu as classes anteriores. Existe como objeto para que a árvore de
    prova registre *por que* a classe foi atribuída.
    """

    fonte: str = ""


# ------------------------------------------------------------------ regra ---

@dataclass(frozen=True)
class Regra:
    """Uma classe do 1º nível categórico e a condição que a define."""

    classe: str
    condicao: Condicao
    fonte: str = ""
    #: Conferida contra o **capítulo** de definição, e não apenas contra a
    #: chave. A distinção não é formalidade: a chave da 5ª edição omite
    #: exclusões que o capítulo enuncia, e transcrevê-la sozinha produz um
    #: sistema que reproduz a chave e diverge da norma.
    verificada_no_capitulo: bool = False
    #: `True` quando a ordem está no recorte implementado a fundo; `False`
    #: quando entra apenas para preservar a precedência da chave.
    no_recorte: bool = False
    observacao: str = ""
