"""Núcleo Simbólico — a única autoridade sobre a classe taxonômica.

Invariante do sistema (monografia, §4.1):

    Nenhuma saída afirma uma classe que a base de regras não derive da norma.

O núcleo formaliza a chave do SiBCS **5ª edição** (SANTOS et al., 2018) em
`chave5.py` — é a base de produção do **ClasSolosBR-NS5**, escolhida porque é a
edição que o sistema de referência implementa e sob a qual os dois acervos
disponíveis foram rotulados. A base da **6ª edição** (SANTOS et al., 2025)
permanece em `chave6.py` como contraprova, e `edicoes.py` classifica o mesmo
perfil sob as duas e nomeia a causa da divergência. A
decisão de projeto que organiza o módulo está em `regras.py`: as regras são
**dados**, não código. Um avaliador separado (`avaliador.py`) percorre essa
estrutura e devolve, além da decisão, o registro da derivação — de onde saem,
sem esforço adicional:

* a **árvore de prova** (para rastreabilidade);
* a **árvore de falha** (insumo do Explicador de Divergências);
* a **distância ao limiar** violado (insumo da abdução contrastiva);
* a avaliação em **três valores**, que sustenta o Avaliador Parcial.

⚠️ A chave publicada não é a especificação completa da norma. Condições
necessárias residem nos capítulos de definição das classes — ver a nota em
`chave5.py` e o cotejo em `[[diff-sibcs-5ed-6ed-classolosbr]]`. Isso é mais
grave na 5ª edição, que enuncia na prosa dos capítulos exclusões que a 6ª passou
a fazer pela posição na chave. Cada regra declara em `fonte` de onde foi
elicitada e se foi conferida contra o capítulo.
"""

# A saída usa →, ✅, ⚠️ e nomes acentuados. No console do Windows o stdout sai
# em cp1252 e qualquer um deles derruba `python -m nucleo.cli`, `-m nucleo.avaliacao`
# e `-m nucleo.testes` com UnicodeEncodeError, depois de já ter impresso parte do
# relatório. Como todo ponto de entrada importa este pacote, basta reconfigurar aqui.
import sys as _sys

for _fluxo in (_sys.stdout, _sys.stderr):
    if hasattr(_fluxo, "reconfigure"):
        _fluxo.reconfigure(encoding="utf-8", errors="replace")

from .logica import V3
from .perfil import Horizonte, Perfil
from .regras import Regra
from .avaliador import classificar, avaliar
from .edicoes import EDICAO_PADRAO, chave_de, cotejar

__all__ = ["V3", "Horizonte", "Perfil", "Regra", "classificar", "avaliar",
           "EDICAO_PADRAO", "chave_de", "cotejar"]
