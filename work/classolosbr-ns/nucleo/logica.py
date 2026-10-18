"""Lógica de três valores (Kleene forte).

Por que três valores, e não dois: o sistema de referência devolve
`"unknown"` (o resultado *desconhecido* da monografia) quando os dados não
satisfazem nenhuma ordem, sem informar o que falta — e sem separar o atributo
ausente do atributo que refuta. A alternativa adotada aqui (monografia,
§4.2.4) é distinguir **falso** de **indeterminado** (convenção de
2026-10-15: "desconhecido" é a saída do sistema de referência;
"indeterminado", o valor I deste núcleo):

    F  a norma refuta a classe
    I  falta evidência para decidir
    V  a norma satisfaz a classe

Daí decorre a propriedade de corretude do Avaliador Parcial: uma classe só é
descartada quando a norma a descarta, de modo que o conjunto de classes
alcançáveis **contém necessariamente a classe verdadeira**. Isso é
demonstrável a partir das tabelas abaixo e não depende de treinamento,
calibração ou qualidade de dado.

Tabelas (Kleene forte):

    E:  F ∧ x = F  para todo x        (basta um falso)
        V ∧ V = V ; demais → I
    OU: V ∨ x = V  para todo x        (basta um verdadeiro)
        F ∨ F = F ; demais → I
    NÃO: ¬V = F ; ¬F = V ; ¬I = I
"""

from __future__ import annotations

from enum import Enum


class V3(Enum):
    """Valor de verdade em três estados."""

    VERDADEIRO = "V"
    FALSO = "F"
    INDETERMINADO = "I"

    def __str__(self) -> str:  # pragma: no cover - conveniência de exibição
        return self.value


V, F, I = V3.VERDADEIRO, V3.FALSO, V3.INDETERMINADO


def e3(valores) -> V3:
    """Conjunção. Um falso basta para refutar, mesmo com indeterminados."""
    visto_i = False
    for v in valores:
        if v is F:
            return F
        if v is I:
            visto_i = True
    return I if visto_i else V


def ou3(valores) -> V3:
    """Disjunção. Um verdadeiro basta para satisfazer."""
    visto_i = False
    for v in valores:
        if v is V:
            return V
        if v is I:
            visto_i = True
    return I if visto_i else F


def nao3(valor: V3) -> V3:
    """Negação. O indeterminado é seu próprio complemento."""
    if valor is V:
        return F
    if valor is F:
        return V
    return I
