"""Intervalos para as proporções reportadas (monografia, §3.5, mitigação 11).

* **Wilson (95%)** para toda proporção. Permanece informativo junto aos
  limites da escala, onde o intervalo usual degenera: 94 em 94 dá
  [96,1%, 100%], e não [100%, 100%].
* **Reamostragem por grupo** (*bootstrap*): a unidade reamostrada é o grupo
  de observações dependentes — o levantamento, no acervo nacional; o perfil,
  nos erros injetados, que são aplicados repetidamente ao mesmo perfil.

Só biblioteca padrão: o núcleo roda sem dependências.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence


def wilson(acertos: int, total: int, z: float = 1.959963984540054
           ) -> tuple[float, float, float]:
    """(proporção, limite inferior, limite superior) pelo método de Wilson."""
    if total == 0:
        return (math.nan, math.nan, math.nan)
    p = acertos / total
    z2 = z * z
    centro = (p + z2 / (2 * total)) / (1 + z2 / total)
    meia = (z / (1 + z2 / total)) * math.sqrt(
        p * (1 - p) / total + z2 / (4 * total * total))
    lo, hi = max(0.0, centro - meia), min(1.0, centro + meia)
    # Ruído de ponto flutuante: 0,9999999999999999 é 1.
    lo = 0.0 if lo < 1e-12 else lo
    hi = 1.0 if hi > 1 - 1e-12 else hi
    return (p, lo, hi)


def bootstrap_por_grupo(grupos: Sequence[Sequence[int]], reamostras: int = 2000,
                        semente: int = 20261015, nivel: float = 0.95
                        ) -> tuple[float, float]:
    """Intervalo percentil para a proporção, reamostrando grupos inteiros.

    `grupos` é uma lista de grupos; cada grupo, a lista de resultados 0/1
    das observações que ele contém.
    """
    grupos = [list(g) for g in grupos if len(g)]
    if not grupos:
        return (math.nan, math.nan)
    rng = random.Random(semente)
    estimativas = []
    for _ in range(reamostras):
        amostra = [grupos[rng.randrange(len(grupos))] for _ in grupos]
        n = sum(len(g) for g in amostra)
        estimativas.append(sum(sum(g) for g in amostra) / n)
    estimativas.sort()
    cauda = (1 - nivel) / 2
    lo = estimativas[int(cauda * reamostras)]
    hi = estimativas[min(reamostras - 1, int((1 - cauda) * reamostras))]
    return (lo, hi)


def auc(positivos: Iterable[float], negativos: Iterable[float]) -> float:
    """Área sob a curva ROC pela estatística de Mann-Whitney (empates = ½)."""
    pos, neg = list(positivos), list(negativos)
    if not pos or not neg:
        return math.nan
    rotulados = sorted([(x, 1) for x in pos] + [(x, 0) for x in neg])
    soma_postos, i = 0.0, 0
    while i < len(rotulados):
        j = i
        while j < len(rotulados) and rotulados[j][0] == rotulados[i][0]:
            j += 1
        posto_medio = (i + 1 + j) / 2
        soma_postos += posto_medio * sum(r for _, r in rotulados[i:j])
        i = j
    n1, n0 = len(pos), len(neg)
    return (soma_postos - n1 * (n1 + 1) / 2) / (n1 * n0)


def fmt(p: tuple[float, float, float] | float, lo: float | None = None,
        hi: float | None = None) -> str:
    """'62,5% [IC 95%: 40,6%–80,0%]', no padrão da monografia."""
    if isinstance(p, tuple):
        p, lo, hi = p
    def pct(x):
        # Junto aos limites, uma casa decimal arredonda 99,99% para 100,0% e
        # faz o intervalo parecer degenerado — o que a mitigação 11 proíbe.
        casas = 2 if (0.999 <= x < 1 or 0 < x <= 0.001) else 1
        return f"{100 * x:.{casas}f}%".replace(".", ",")
    if lo is None:
        return pct(p)
    return f"{pct(p)} [{pct(lo)}–{pct(hi)}]"
