"""Inferidor de Horizonte Diagnóstico (monografia, §4.2.5) — o componente neural.

Aprende, sobre os horizontes do acervo nacional, a associação entre os
atributos do horizonte (com o contexto no perfil) e o símbolo anotado pelo
pedólogo, e devolve, para cada horizonte, o horizonte principal e os sufixos
propostos, com confiança. Três restrições (§4.2.5): a saída é um **símbolo**,
nunca uma classe; o componente **não sobrescreve** o símbolo anotado; e o
símbolo proposto só alimenta o núcleo quando o anotado falta ou não informa o
tipo, com a classe resultante apresentada como condicional.

Módulos:
    dados      — conjunto de horizontes, atributos, rótulos e partição
    modelos    — a rede (perceptron multicamadas) e as duas linhas de base
    avaliacao  — `python -m inferidor.avaliacao`: inferência e uso efetivo
"""
