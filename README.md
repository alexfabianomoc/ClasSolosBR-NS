# ClasSolosBR-NS

Código do Trabalho Final de Graduação "ClasSolosBR-NS: arquitetura neuro-simbólica para explicação de divergências na classificação de solos pelo SiBCS", de Alex Fabiano Silva (Engenharia de Computação, 2026).

O núcleo simbólico formaliza a chave do Sistema Brasileiro de Classificação de Solos (SiBCS) na 5ª edição (SANTOS et al., 2018), com a base da 6ª edição (2025) como contraprova no primeiro nível, avaliada em lógica de três valores.

## Conteúdo

| Caminho | O que é |
|---|---|
| `work/classolosbr-ns/nucleo/` | Núcleo simbólico: bases de regras da 5ª e da 6ª edição, avaliador em três valores, Avaliador Parcial (conjunto alcançável e próxima medição), Explicador de Divergências, Camada de Versão e avaliações (`python -m nucleo.testes`, `nucleo.avaliacao`, `nucleo.avaliacao_bdsolos`, …) |
| `work/classolosbr-ns/inferidor/` | Inferidor de Horizonte Diagnóstico (perceptron multicamadas e classificador de árvores de gradiente), avaliado isoladamente |
| `work/classolosbr-ns/dags/` | Preparação de dados: fluxos Bronze e Prata (Airflow, Spark, Delta) e o Sentinela de Qualidade de Dados |
| `work/classolosbr-ns/transcricao/` | Transcrição das fichas originais do conjunto curado para o formato de entrada |
| `tools/bdsolos_adapter.py` | Instrumento de conversão do Banco de Dados de Solos do Brasil (275 colunas) para o contrato de entrada da API SmartSolos Expert |
| `tools/agroapi_*.py`, `tools/linha_base*.py` | Cliente da API SmartSolos Expert (AgroAPI/Embrapa) e medição da linha de base |

A estrutura de pastas espelha a do projeto original, porque os módulos localizam os dados e as ferramentas por caminho relativo (`raw/` e `tools/` na raiz).

## Dados

Os dados não estão neste repositório. São da Embrapa, publicados no Repositório de Dados de Pesquisa da Embrapa sob licença CC BY-NC 4.0, e devem ser baixados à parte. Ver `raw/README.md`.

## Executar

O 4º nível (subgrupos) lê as definições da norma de `work/classolosbr-ns/nucleo/dados/subgrupos5.json`, que **não é distribuído**: reproduziria o texto do SiBCS, obra com todos os direitos reservados pela Embrapa. Gere-o a partir do PDF da 5ª edição, distribuído gratuitamente pela Embrapa:

```bash
pdftotext -enc UTF-8 -layout sibcs-5a-edicao.pdf sibcs.txt
cd work/classolosbr-ns
python -m nucleo.subgrupos_texto ../../sibcs.txt --saida nucleo/dados/subgrupos5.json
```


Python 3.11 ou superior. O núcleo usa só a biblioteca padrão; o Inferidor e a preparação de dados têm as dependências de `work/classolosbr-ns/requirements.txt`.

```bash
cd work/classolosbr-ns
python -m nucleo.testes            # verificações automatizadas
python -m nucleo.avaliacao         # conjunto curado
python -m nucleo.avaliacao_bdsolos # acervo nacional, primeiro nível
```

A medição da linha de base (`tools/linha_base.py coletar`) exige credencial da AgroAPI, lida de `~/.agroapi.json` (`consumer_key`, `consumer_secret`) e nunca versionada.

## Licença

Código sob a [PolyForm Noncommercial License 1.0.0](LICENSE.md): uso, cópia e modificação livres para fins não comerciais. Os dados de terceiros seguem as licenças de origem.
