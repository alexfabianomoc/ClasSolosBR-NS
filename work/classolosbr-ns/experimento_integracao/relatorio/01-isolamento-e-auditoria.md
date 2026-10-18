# 1. Isolamento e auditoria do estado encontrado

> Nota da publicação: caminhos locais da estação de trabalho substituídos por marcadores (`<cópia experimental>`, `<projeto original>`); o restante do texto é o do registro original.

*Data: 2026-10-18. Tudo nesta pasta foi produzido na cópia experimental.*

## 1.1 Isolamento

| Item | Valor |
|---|---|
| Projeto original | `<projeto original>` (vault inteiro: `work/classolosbr-ns/`, `raw/`, `tools/`, `wiki/`) e `<diretório dos documentos acadêmicos>` (fontes LaTeX, PDF, `ref.bib`, figuras da monografia e do artigo) |
| Controle de versão | o diretório **não é repositório Git** (`.git` inexistente em toda a árvore); não havia "alterações não commitadas" a preservar — o estado é o dos arquivos |
| Cópia experimental | `<cópia experimental>`, que reproduz a mesma relação de pastas (os caminhos relativos `parents[3] / "raw"` do código continuam válidos) |
| Método | `shutil.copytree(symlinks=False, copy_function=copy2)`: cópia byte a byte, sem links simbólicos nem *hard links*; não se usou `git clone` |
| Manifesto | `_isolamento/manifesto.py` (SHA-256, tamanho, mtime). Antes da cópia: 906 arquivos / 445.034.978 bytes no vault e 71 / 13.100.188 no diretório LaTeX; 0 erros de leitura, 0 links. A cópia conferiu **906/906 e 71/71 idênticos** (`comparar`: 0 só-em-A, 0 só-em-B, 0 diferentes) |
| Exclusões | nenhuma. O `.gitignore` do vault exclui o CSV do BDSolos e as fichas RTF do versionamento, mas eles **estão no disco** e foram copiados (o CSV é necessário ao treino) |
| Caminhos absolutos | nenhum no código; o único em `tools/search.py` é exemplo em docstring. Todas as gravações do código são relativas a `__file__` e, na cópia, caem na cópia |
| Proteção dentro da cópia | 842 arquivos marcados **somente leitura**: `raw/`, `wiki/` (monografia compilada, avulsos, rascunho, páginas), `tools/dados/`, `work/classolosbr-ns/{resultados, transcricao/originais, nucleo/dados, _historico}` e toda a árvore LaTeX copiada |
| Ambiente | `.venv` próprio da cópia (CPython 3.13.2; scikit-learn 1.9.0, NumPy 2.2.4, joblib 1.6.0, SciPy 1.18.1 — as mesmas versões registradas no log do wiki para o treino de 2026-10-17); o Python do sistema não foi alterado |
| Git, push, merge, publicação | nenhum |
| Saídas novas | só em `work/classolosbr-ns/integracao/` (código) e `work/classolosbr-ns/experimento_integracao/` (config, modelos, resultados, relatório, exemplos), mais `nucleo/dados/catalogo_simbolo_ausente.json` e a alteração declarada de `nucleo/avaliador.py` |

## 1.2 Componentes: o que existia, o que estava isolado, o que faltava

| Componente | Estado encontrado (código e artefatos) | Lacuna para o fluxo completo |
|---|---|---|
| Núcleo Simbólico versionado | `nucleo/` — chaves da 5ª (`chave5.py`, produção) e da 6ª (`chave6.py`), regras como dados, avaliador em três valores com árvores de prova e de falha. `nucleo.testes` passa | — (mas ver os defeitos C1–C4, §2) |
| Sentinela de Qualidade de Dados | gramática de símbolos (`dags/sentinela/gramatica_sufixos.py`) e escore de anomalia por escore z robusto (`dags/sentinela/anomalia.py`). Usado pelo Explicador só nos scripts de avaliação | não era chamado por nenhum fluxo de classificação |
| Camada de Versão | `nucleo/edicoes.py` (`cotejar`, causas da não conclusão, `assimetrias`) | executada à parte (`nucleo.cli cotejar`); o Explicador não a consultava |
| Avaliador Parcial | conjunto alcançável (lógica de Kleene) + `nucleo/medicao.py` (próxima determinação por ganho de informação com doadores do BDSolos) | recomendação só por linha de comando |
| Inferidor de Horizonte Diagnóstico | `inferidor/` — 81 atributos, rótulos do símbolo, rede (MLP) e árvores; `inferidor.avaliacao` e `inferidor.selecao` | **nenhum artefato salvo** (`rede.joblib` nunca gravado); nenhuma interface de inferência; avaliado isoladamente |
| Explicador de Divergências | `nucleo/explicador.py` — abdução de um atributo numérico, verificação por reexecução, escore s(h) com o Sentinela | símbolo de horizonte **declaradamente fora** ("Símbolo de horizonte (que viria do Inferidor) … ficam fora"); sem Camada de Versão |

## 1.3 Estimadores do Inferidor (estado real, conferido no código e reexecutado)

Os números da monografia saem de `inferidor/selecao.py`, não de `inferidor/avaliacao.py`
(que dá a rodada anterior, também reproduzida). Reproduções bit a bit na cópia
(`resultados/etapa0_reproducao/`):

| | `inferidor.avaliacao` (1ª rodada) | `inferidor.selecao` (números da monografia) |
|---|---|---|
| Rede | MLP (128, 64): principal 76,4%, F1 macro 0,236 | **MLP (256, 128), α = 1e-4: 77,0% [75,6–78,3], F1 0,279** |
| Não neural | árvores, taxa 0,1: 77,9%, 0,212 | **árvores, taxa 0,05: 79,7% [78,3–80,9], F1 0,322** |
| Mais frequente | 46,0%, 0,052 | 46,0%, 0,052 |

**Estimador não neural efetivamente usado:** `sklearn.ensemble.HistGradientBoostingClassifier`
— um classificador multiclasse para o horizonte principal e **um classificador binário por
sufixo** (17), com `max_iter=300`, `learning_rate=0.05` (escolhida entre 0,05/0,1/0,2 na
validação interna), `random_state=20261017`, demais hiperparâmetros no padrão do scikit-learn
1.9.0. ⚠️ O padrão `early_stopping="auto"` **está ativo** no treino (conferido no artefato:
`do_early_stopping_ = True`): o modelo do principal parou em 105 iterações e os dos sufixos entre
10 e 300 — o "max_iter=300" é teto, não número de árvores. Sufixo constante no treino vira
constante. Das 81 colunas, 73 têm dois ou mais valores distintos e entram nos dois modelos. As
duas MLPs pararam por *early stopping* em 16 (principal) e 22 (sufixos) épocas.

**Pré-processamento:** comum — os 81 atributos de `inferidor.dados.atributos` (próprios,
derivados do complexo sortivo, posição, vizinhos acima e abaixo, indicadores de ausência
de matiz neutro); colunas sem dois valores distintos descartadas; principais com menos de 20
exemplos agrupados em "outro". Rede: `SimpleImputer(median, add_indicator=True)` +
`StandardScaler` + `MLPClassifier(early_stopping, validation_fraction=0.1, max_iter=300)`.
Árvores: **sem imputação** (o HistGradientBoosting trata o ausente nativamente). Limiar por
sufixo escolhido na validação (F1 do sufixo), nos dois. Partição por levantamento
(GroupShuffleSplit, semente 20261017; validação interna com 20261018).

Confirmado também: a rede **não** estava integrada ao núcleo; o conflito anotado × inferido não
era hipótese do Explicador; a Camada de Versão não era consultada pelo Explicador — como diz a
monografia.
