"""A rede do Inferidor e as duas linhas de base da §4.2.5.

* **Rede**: perceptron multicamadas (scikit-learn), uma para o horizonte
  principal (multiclasse) e outra para os 17 sufixos lidos (multirrótulo).
  Entrada: atributos imputados pela mediana, com indicador de ausência, e
  padronizados. Parada antecipada sobre 10% do treino.
* **Linha de base 1 — sufixo mais frequente para o tipo de horizonte**: o
  principal mais frequente do treino; para os sufixos, o conjunto mais
  frequente entre os horizontes de mesmo principal **anotado** (o que dá a ela
  uma vantagem: conhece o principal verdadeiro).
* **Linha de base 2 — classificador não neural de mesma entrada**: árvores
  de gradiente (HistGradientBoosting), que lidam com o valor ausente sem
  imputação; um modelo para o principal e um por sufixo.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEMENTE = 20261017
OUTRO = "outro"
MINIMO_CLASSE = 20


def agrupa_raros(principais, minimo=MINIMO_CLASSE):
    """Principais com menos de `minimo` exemplos viram 'outro' (a parada
    antecipada estratifica e não admite classe com um exemplo)."""
    n = Counter(principais)
    return np.array([p if n[p] >= minimo else OUTRO for p in principais])


def colunas_informativas(X):
    """Colunas com pelo menos dois valores distintos (fora o ausente) — as
    demais não informam nada, e as árvores de gradiente não as aceitam.
    Atributos que o acervo nunca preenche (caracteres por horizonte, §3.5)
    caem aqui."""
    return np.array([len(np.unique(c[~np.isnan(c)])) >= 2 for c in X.T])


def _mlp():
    return make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=(128, 64), early_stopping=True,
                      validation_fraction=0.1, max_iter=300, random_state=SEMENTE),
    )


class Rede:
    nome = "rede neural (MLP)"

    def fit(self, X, principal, sufixos):
        self.colunas = colunas_informativas(X)
        X = X[:, self.colunas]
        self.p = _mlp().fit(X, principal)
        self.s = _mlp().fit(X, sufixos)
        return self

    def predict(self, X):
        X = X[:, self.colunas]
        return self.p.predict(X), self.s.predict(X)

    def predict_proba(self, X):
        X = X[:, self.colunas]
        return self.p.predict_proba(X), self.s.predict_proba(X)


class Arvores:
    nome = "não neural (árvores de gradiente)"

    def fit(self, X, principal, sufixos):
        self.colunas = colunas_informativas(X)
        X = X[:, self.colunas]
        kw = dict(max_iter=300, random_state=SEMENTE)
        self.p = HistGradientBoostingClassifier(**kw).fit(X, principal)
        self.s = []
        for j in range(sufixos.shape[1]):
            y = sufixos[:, j]
            self.s.append(HistGradientBoostingClassifier(**kw).fit(X, y)
                          if y.min() != y.max() else int(y[0]))
        return self

    def predict(self, X):
        X = X[:, self.colunas]
        cols = [np.full(len(X), m) if isinstance(m, int) else m.predict(X) for m in self.s]
        return self.p.predict(X), np.column_stack(cols)


class MaisFrequente:
    nome = "mais frequente (sufixo por tipo de horizonte)"

    def fit(self, X, principal, sufixos):
        self.p = Counter(principal).most_common(1)[0][0]
        por = defaultdict(Counter)
        for pr, s in zip(principal, map(tuple, sufixos)):
            por[pr][s] += 1
        self.s = {pr: np.array(c.most_common(1)[0][0]) for pr, c in por.items()}
        self.s_geral = np.array(Counter(map(tuple, sufixos)).most_common(1)[0][0])
        return self

    def predict(self, X, principal_anotado=None):
        n = len(X)
        p = np.full(n, self.p, dtype=object)
        if principal_anotado is None:
            s = np.tile(self.s_geral, (n, 1))
        else:
            s = np.vstack([self.s.get(pr, self.s_geral) for pr in principal_anotado])
        return p, s
