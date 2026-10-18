"""Sentinela — escore de anomalia por atributo (monografia, §4.2.2 e §4.3.2).

Primeira função do Sentinela: atribuir a cada **atributo** de um perfil um
escore σ em [0, 1] que diga o quanto o valor informado destoa do padrão dos
perfis de referência. O escore incide sobre o atributo, e não sobre o perfil:
o Explicador precisa saber **qual** valor é suspeito.

Algoritmo adotado: **escore z robusto** — distância à mediana em unidades de
desvio absoluto mediano (MAD × 1,4826) —, calculado por atributo e
condicionado ao tipo de horizonte principal (A, B, C, E…), com recuo para a
distribuição global do atributo quando o grupo tem menos de `minimo_grupo`
valores. As concentrações são lidas em escala logarítmica, porque o erro que
o registro de curadoria documenta é multiplicativo (separador decimal, ×10);
pH e cor Munsell, em escala linear.

Por que este, e não um modelo de maior capacidade: o conjunto de referência
tem 94 perfis (444 horizontes), e o rótulo que um modelo supervisionado
exigiria — qual tratamento cada perfil demandou — está disponível apenas no
texto do registro de curadoria e sobre os dados **já corrigidos**. Um método
sem parâmetros aprendidos além de mediana e MAD não ajusta ruído amostral, e
cada escore pode ser lido e conferido à mão, como "este valor está a tantos
MADs da mediana dos horizontes B". Hiperparâmetros: `minimo_grupo` (8) e a
constante de saturação de σ (3, isto é, σ = 0,5 a três MADs).

O Sentinela não classifica: o escore só ordena hipóteses e alimenta alertas.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

#: Atributos lidos em escala linear (já logarítmicos ou ordinais).
LINEARES = {"PH_AGUA", "PH_KCL"}
_DESLOCAMENTO_LOG = 0.01
_SATURACAO = 3.0
_PRINCIPAL = re.compile(r"[A-Z]")


def horizonte_principal(simbolo: str) -> str:
    """Primeira maiúscula do símbolo — 'A' em 'Ap', 'B' em '2Bt', 'A' em 'AB'."""
    m = _PRINCIPAL.search(simbolo or "")
    return m.group(0) if m else "?"


def _transforma(atributo: str, valor: float) -> float:
    if atributo in LINEARES or atributo.startswith("COR_"):
        return valor
    return math.log10(max(valor, 0.0) + _DESLOCAMENTO_LOG)


def _mediana(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


class DetectorAnomalia:
    """Escore z robusto por atributo e tipo de horizonte."""

    def __init__(self, minimo_grupo: int = 8) -> None:
        self.minimo_grupo = minimo_grupo
        self._ref: dict[tuple[str, str], tuple[float, float]] = {}

    def ajustar(self, perfis) -> "DetectorAnomalia":
        valores: dict[tuple[str, str], list[float]] = defaultdict(list)
        for p in perfis:
            for h in p.horizontes:
                g = horizonte_principal(h.simbolo)
                for a, v in h.atributos.items():
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        continue
                    x = _transforma(a, float(v))
                    valores[(g, a)].append(x)
                    valores[("*", a)].append(x)
        self._ref = {}
        for chave, xs in valores.items():
            if len(xs) < (self.minimo_grupo if chave[0] != "*" else 2):
                continue
            med = _mediana(xs)
            mad = _mediana([abs(x - med) for x in xs]) * 1.4826
            if mad == 0:
                # Distribuição concentrada num valor: usa o desvio absoluto
                # médio, e um piso para não dividir por zero.
                mad = sum(abs(x - med) for x in xs) / len(xs) or 0.05
            self._ref[chave] = (med, mad)
        return self

    def z_valor(self, simbolo: str, atributo: str, valor) -> float | None:
        """Escore z robusto de um valor, para um horizonte com este símbolo."""
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None
        ref = (self._ref.get((horizonte_principal(simbolo), atributo))
               or self._ref.get(("*", atributo)))
        if ref is None:
            return None
        med, mad = ref
        return (_transforma(atributo, float(valor)) - med) / mad

    def z(self, perfil, indice: int, atributo: str) -> float | None:
        h = perfil.horizontes[indice]
        return self.z_valor(h.simbolo, atributo, h.get(atributo))

    def escore_valor(self, simbolo: str, atributo: str, valor) -> float:
        """σ = |z| / (|z| + 3): 0 na mediana, 0,5 a três MADs, → 1."""
        z = self.z_valor(simbolo, atributo, valor)
        if z is None:
            return 0.0
        return abs(z) / (abs(z) + _SATURACAO)

    def escore(self, perfil, indice: int, atributo: str) -> float:
        h = perfil.horizontes[indice]
        return self.escore_valor(h.simbolo, atributo, h.get(atributo))
