# ClasSolosBR-NS5 — protótipo do pipeline medallion

> **Nota de nomenclatura (2026-09-11).** O sistema passou a se chamar
> **ClasSolosBR-NS5**: a camada simbólica de produção é a da **5ª edição** do
> SiBCS. O NS6 passou a ser tratado como proposta de evolução. Ver
> [[projeto-neuro-simbolico-classolosbr]].
>
> **Atualização (2026-10-11).** A versão saiu de **todos** os nomes derivados do
> projeto, porque a chave taxonômica é escolhida em tempo de execução
> (`chave5.py` / `chave6.py`) e o mesmo sistema atende às duas edições. O
> diretório passou a `work/classolosbr-ns/`; o banco, a `classolosbr_ns`; a
> imagem, a `classolosbr-ns/airflow:0.1.0`; as tags dos dois DAGs, a
> `classolosbr-ns`; e o **nome do projeto Compose agora é fixado** em
> `name: classolosbr-ns`, para não voltar a depender da pasta.
>
> ✅ **Não há migração a fazer.** A renomeação só seria custosa numa stack já
> provisionada, e **esta nunca subiu**: o log do wiki registra em 2026-08-24
> que o DAG foi validado simulando a lógica em pandas, com a ressalva "não
> executado no Airflow — exige a stack Docker de pé", e o disco de dados do
> Docker Desktop não é escrito desde 28/05/2026, antes de este projeto existir.
> Na primeira subida os quatro volumes nascem já como `classolosbr-ns_<nome>`,
> o `init-db/` roda em volume vazio e cria o banco `classolosbr_ns` — o mesmo
> valor de `GOLD_DB`. Basta `docker compose up -d`.
>
> **Conferência (2026-10-15).** Números do núcleo, da Prata e as listas de
> pendências revistos contra o código e a execução de `nucleo.testes`,
> `nucleo.cli lote` e `nucleo.avaliacao`. A versão anterior está em
> `_historico/README-2026-10-15-antes-da-atualizacao.md`.
>
> ⚠️ Acoplamento a conhecer: o nome do banco está **fixo** no SQL de
> `init-db/01-cria-banco-ouro.sql` (o entrypoint do Postgres não expande
> variável de shell ali), e repetido em `GOLD_DB`. Mudar um sem o outro passa
> em silêncio. Hoje os dois dizem `classolosbr_ns`.

Stack local para as camadas Bronze / Prata / Ouro sobre o BDSolos.
Documentação conceitual: [[implementacao-classolosbr-ns-medallion-lakehouse]].

## Por que a stack é enxuta por padrão

O BDSolos tem **97 MB · 34.108 horizontes · 8.925 perfis · 275 colunas**
(verificado contra o arquivo em 2026-08-31). Isso cabe na RAM de um notebook.
O Spark roda em **local mode dentro do contêiner do Airflow** — subir um
cluster acrescentaria coordenação de rede a um trabalho que dura segundos.

O cluster Spark e o par Prometheus/Grafana existem como **profiles opcionais**,
para quando o objetivo for demonstrar a arquitetura distribuída (capítulo de
arquitetura da monografia) e não processar o dado mais rápido.

## Subir

```bash
cp .env.example .env    # e troque as senhas
docker compose up -d --build
```

Serviços: Airflow <http://localhost:8080> · MinIO <http://localhost:9001>
· PostgreSQL `localhost:5432`.

Opcionais:

```bash
docker compose --profile spark up -d
docker compose --profile monitoring up -d
```

## Executar a ingestão Bronze

O DAG `bronze_ingest_bdsolos` é de disparo manual (`schedule=None`) — a fonte
é um dataset publicado, não um fluxo contínuo.

```bash
docker compose exec airflow-scheduler airflow dags unpause bronze_ingest_bdsolos
```

Depois dispare pela UI, ou:

```bash
docker compose exec airflow-scheduler airflow dags trigger bronze_ingest_bdsolos
```

O DAG é **idempotente**: grava o SHA-256 do CSV num manifesto no bucket Bronze
e encerra sem escrever se o mesmo arquivo já tiver sido ingerido.

## Executar a transformação Prata

```bash
docker compose exec airflow-scheduler airflow dags trigger prata_transforma_bdsolos
```

Produz três saídas em `s3a://silver/`:

| Saída | Grão | Linhas |
|---|---|---:|
| `perfis/` (Delta) | um por perfil | 8.923 |
| `horizontes/` (Delta) | um por horizonte descrito | 33.327 |
| `_rejeitados/` (Parquet) | um por linha com problema, **com motivo** | variável |

Mais um relatório de qualidade em `s3a://silver/_qualidade/prata-*.json`.

### O princípio: sinaliza, não filtra

Perfil sem horizonte (750) e perfil sem coordenada (5.605) **permanecem** na
tabela, marcados por flag — `tem_horizonte`, `tem_coordenada`,
`coordenada_no_brasil`, `coordenada_impossivel`, `ordem_valida`,
`foi_reclassificado`, `atributos_divergentes`. Quem consome decide o recorte;
o pipeline não decide por ele.

### Números medidos na fonte (conferidos contra `ESPERADO` em 2026-10-15)

A validação da Prata falha se qualquer um destes divergir:

| | |
|---|---:|
| Linhas Bronze | 34.108 |
| Registros partidos na origem | 6 |
| Perfis | 8.923 |
| Perfis descartados por registro corrompido | 1 |
| Horizontes | 33.327 |
| Perfis sem horizonte | 750 |
| Perfis com horizonte | 8.173 |

> **Por que 8.923 e 750, e não 8.925 e 752 (achado de 2026-10-14).** Em três
> horizontes do perfil `797|12743|RS-142`, o material de origem traz aspas
> internas sem escape, e o leitor parte cada registro em dois: são os **seis
> registros partidos**. As metades formam um perfil que não existe. A Prata
> marca os seis com `_f_registro_partido`, rejeita com motivo e os tira dos dois
> grãos; o perfil real, sem nenhum registro legível, é contado à parte
> (`perfis_descartados_corrompidos` = 1). A Bronze continua contando 34.108 / 8.925, porque preserva o
> arquivo como veio. ⚠️ Os novos valores foram conferidos por simulação em
> Python; o DAG não rodou no Spark.

E as flags, medidas mas **não** usadas como critério de falha: 5.605 sem
coordenada · 18 fora do Brasil · 9 com coordenada impossível · 499 sem ordem ·
3.918 reclassificados · 13 com atributos divergentes · 273 horizontes com
profundidade invertida.

⚠️ As flags foram medidas sobre os 8.925 perfis da Bronze (2026-08-31), antes do
descarte dos registros partidos. Elas podem mudar em uma ou duas unidades na
primeira execução real da Prata. Os reclassificados passaram de 3.999 para
**3.918** em 2026-09-18: a comparação deixou de ser byte a byte e ignora caixa,
espaço, ponto final e acento (ver `_classificacao_comparavel`).

## Estrutura

```
docker-compose.yml   stack (4 serviços padrão + 2 profiles opcionais)
Dockerfile           Airflow + Java 17 + PySpark 3.5.1 + Delta 3.2.0
requirements.txt     versões fixadas (a matriz Spark/Delta/Hadoop tem que casar)
.env.example         configuração; copie para .env
init-db/             cria o banco e o schema `ouro` no PostgreSQL
dags/                DAGs do Airflow
  bronze_ingest_bdsolos.py
  prata_transforma_bdsolos.py
  sentinela/         verificações que sinalizam, nunca filtram
    gramatica_sufixos.py   norma de símbolos de horizonte
    relatorio.py           apura a gramática sobre um corpus
```

## Sentinela — gramática dos símbolos de horizonte

`SIMB_HORIZ` não é rótulo descritivo: é a entrada que decide a classe no motor
de referência. Símbolo malformado não gera erro — gera classificação errada em
silêncio. `sentinela/gramatica_sufixos.py` formaliza a norma para que o símbolo
possa ser conferido.

Fonte: **Lemos & Santos (1996)**, súmula de sufixos (p. 47-48) e tabela de
aplicabilidade por horizonte (p. 49) — uma das duas obras a que a 6ª edição do
SiBCS remete. O SiBCS usa este vocabulário mas não o define.

Roda de dois modos — como task do pipeline e como relatório avulso:

```bash
python -m sentinela.relatorio bdsolos
python -m sentinela.relatorio pykka7 --edicao 2015
python -m sentinela.relatorio bdsolos --detalhar NOTACAO_LEGADA
```

### No pipeline: a task `sinalizar_simbolos`

Roda depois de `validar`, no DAG `prata_transforma_bdsolos`, e grava em
`s3a://silver/achados_simbolo/` — **tabela separada de `horizontes`**, que não é
tocada. Uma linha por horizonte, com o array de achados, a gravidade máxima, a
leitura atual quando o símbolo é legado e o sinalizador `k_barra_candidato`.

⚠️ **Sem UDF, de propósito.** São ~1.473 símbolos distintos para ~33.327
horizontes: validar os distintos no driver e juntar de volta faz 22× menos
avaliações e **não exige enviar o módulo ao executor** — o que quebraria no
profile de cluster sem um `addPyFile`.

A edição da norma vem de `CLASSOLOSBR_EDICAO_NORMA` (padrão `2015`). ⚠️ Ler como
"conforme a 7ª edição": existe uma 8ª (SBCS, 2025, 156 p.) ainda ausente do
acervo.

⚠️ **A task ainda não foi executada contra o Spark.** A lógica do driver foi
verificada fora do pipeline, contra o CSV real, e reproduz os números do
relatório de linha de comando (33.327 horizontes, 1.473 símbolos distintos,
36,4% conformes, 13,7% de notação legada, 5 candidatos a `k̄`). O que falta
confirmar é a parte Spark: a janela de `lead`, o `F.exists` sobre o array de
structs e a escrita em Delta.

Medido em 2026-09-07 (edição 1996):

| | BDSolos | PYKKA7 |
|---|---:|---:|
| horizontes | 33.327 | 444 |
| conformes | 36,5% | 77,3% |
| com **erro** | 2,3% | 0,5% |
| `NOTACAO_LEGADA` | 13,8% | — |
| `SEM_SUFIXO` | 45,7% | 15,1% |

As gravidades separam o que exige revisão do que é só divergência entre norma e
prática:

- **erro** — malformado sob qualquer leitura (`Tradagem` no campo de símbolo).
- **alerta** — contraria a norma, mas a norma é internamente inconsistente em
  alguns pontos; não sustenta rejeição.
- **suspeita** — coerência entre campos aponta perda de informação (ver abaixo).
- **nota** — outra convenção ou prática corrente, não defeito. `SEM_SUFIXO`
  responde por 45,7% do BDSolos porque `A`/`B`/`C` sem sufixo é uso corrente,
  ainda que a norma peça sufixo.

⚠️ **`NOTACAO_LEGADA` é o achado que mais muda a leitura do BDSolos.** 13,8% dos
horizontes usam a convenção anterior ao SiBCS — prefixo em algarismo romano
(`IIB2t`), índice antes do sufixo (`B2t`, hoje `Bt2`) e `(B)` para B incipiente
(hoje `Bi`). Não são defeitos. Antes de reconhecê-los, 13,1% do corpus caía em
"não analisável"; depois, 1,7%. `moderniza()` sugere a forma atual e **nunca
reescreve** — a norma manda confirmar o nome do horizonte contra os dados
analíticos, e essa decisão é do curador.

⚠️ **O sufixo `k̄` não sobrevive a texto simples.** A norma distingue `k`
(carbonatos herdados) de `k̄` (acumulação de carbonato de cálcio secundário) por
uma barra sobre a letra — `k` + U+0304. Em ASCII os dois colapsam. Não há
**nenhuma** ocorrência de U+0304 no BDSolos, no PYKKA7 ou no PDF do SiBCS.
`suspeita_k_barra_perdido()` é a única defesa depois que o dado chega: cruza o
sufixo `k` com o CaCO₃ equivalente e aponta candidatos (5 no BDSolos, 16 no
PYKKA7).

⚠️ **`_sanear()` da Bronze faz `NFKD → encode("ascii", "ignore")`.** Hoje só
roda sobre nomes de coluna. Aplicá-lo a valores destruiria `k̄` sem deixar
traço.

## Núcleo Simbólico — a camada que classifica

`nucleo/` implementa a chave do 1º nível categórico do SiBCS em **duas
edições**. A de produção é a **5ª** (`chave5.py`), porque é a edição que o
sistema de referência implementa e sob a qual os dois acervos foram rotulados;
a **6ª** (`chave6.py`) permanece como contraprova e alimenta a camada
versão-consciente. É a única autoridade sobre a classe: nenhuma saída do
sistema afirma classe que a base de regras não derive da norma.

```bash
python -m nucleo.cli cobertura                       # o que está implementado
python -m nucleo.cli classificar PERFIL.json --prova # com árvore de prova
python -m nucleo.cli classificar PERFIL.json --falhas # pontos de ruptura
python -m nucleo.cli lote ../../raw/pykka7-smartsolos-dataset
python -m nucleo.cli cotejar PERFIL.json             # as duas edições (M3)
python -m nucleo.cli edicoes                         # precedências e assimetrias
python -m nucleo.cli --edicao 6 lote ../../raw/pykka7-smartsolos-dataset
python -m nucleo.testes                              # sem dependências
```

Sobre os 94 perfis curados, cujo rótulo é da 5ª edição (medido em 2026-10-15):

| Base | Concordância no 1º nível | Não conclusivos | Divergentes |
|---|---|---|---|
| 5ª ed. (produção) | 50 (53,2%) | 44 | 0 |
| 6ª ed. (contraprova) | 49 (52,1%) | 45 | 0 |

As saídas das duas bases diferem em **13 dos 94 perfis** (11 com classe
diferente, mais 2 em que muda só o conjunto alcançável), por três causas
(monografia, §5.4):

- **9 perfis — contraste dos Neossolos.** Sob a 5ª edição eles são testados em
  2º lugar com lista de exclusões que o dado disponível não fecha, e a regra
  fica indeterminada; sob a 6ª são a cláusula residual da 13ª posição, que
  dispara.
- **2 perfis — exigência que só a 6ª faz** (`PE_025_Barreiros`,
  `PE_026_Agua_Preta`): o glei dos primeiros 50 cm tem de ocupar a maior parte
  dos 30 cm abaixo do A. A 5ª conclui GLEISSOLO, como a ficha. A 6ª não
  conclui, porque os dois perfis têm 15 cm sem horizonte descrito nessa faixa;
  GLEISSOLO continua alcançável. É diferença normativa real, não efeito de
  formalização.
- **2 perfis (RN_042, RN_044) — só o grau de conclusão ou o conjunto
  alcançável muda**, pela reordenação da chave: a 6ª testa os Plintossolos em
  5º lugar, antes dos Chernossolos, que na 5ª os precedem e, indeterminados,
  impedem a conclusão. Num perfil a 6ª conclui o Plintossolo registrado; no
  outro a indeterminação passa a vir dos Planossolos, cuja regra na 6ª não
  exclui o B plânico coincidente com o plíntico, como a da 5ª exclui.
  (Corrigido em 2026-10-15: antes se atribuíam estes 2 às "exclusões de
  plintita na prosa dos capítulos".)

Em nenhum dos 13 uma classe registrada é refutada sob qualquer das duas bases.
O caso que distingue as edições pela **ordem concluída** — Cambissolo ×
Argissolo, com B incipiente logo abaixo do A e B textural em profundidade —
não ocorre nos 94 perfis. Ele é coberto pelo teste sintético
`teste_divergencia_cambissolo_argissolo`, que devolve CAMBISSOLO sob a 5ª, como
a API, e **indeterminado entre ARGISSOLO e CAMBISSOLO** sob a 6ª — desde
2026-10-15, porque a 6ª é internamente inconsistente sobre a posição do B
textural ("subjacente a" no Cap. 5, "imediatamente abaixo" na Definição do
Cap. 3). Os Luvissolos da 6ª recebem o mesmo tratamento. Antes, a base da 6ª
adotava sem declarar a leitura do item da chave e devolvia ARGISSOLO.

Sem dependências externas — só a biblioteca padrão e `dags/sentinela/`.

### A decisão de projeto: regras como dados

Cada condição da norma é um **objeto** (`regras.py`), não uma função. Um
avaliador separado (`avaliador.py`) percorre a estrutura. A base continua
legível como transcrição da norma, e a instrumentação fica toda no avaliador.

Foi rejeitada a alternativa de adotar uma linguagem lógica com
meta-interpretação, que é o caminho do sistema de referência: repeti-lo não
acrescenta conhecimento, e imporia uma fronteira entre linguagens a cada
perfil, com o restante do protótipo em Python.

Da escolha decorrem, sem esforço adicional, as quatro estruturas de que a
arquitetura depende:

| Estrutura | Para quê |
|---|---|
| árvore de prova | rastreabilidade da classe atribuída |
| árvore de falha | insumo do Explicador de Divergências |
| distância ao limiar | insumo da abdução contrastiva |
| avaliação em 3 valores | Avaliador Parcial, e a propriedade de contenção |

### O símbolo do horizonte é entrada diagnóstica

`horizontes.py` adota a mesma leitura verificada no sistema de referência em
2026-09-07: **o símbolo propõe o tipo diagnóstico, o dado pode vetar, e nada é
proposto pelo dado sozinho**. Inferir o tipo a partir dos atributos é tarefa
do componente 4.2.5, orientado a dados, que fica fora do núcleo — misturá-los
destruiria o invariante.

Cada identificação carrega a `origem`, que atravessa a árvore de prova.

### Recorte e honestidade sobre ele

Cinco ordens estão implementadas a fundo — Latossolos, Argissolos, Luvissolos,
Espodossolos e Cambissolos. As outras oito entram com regra de **triagem**:
preservam a precedência da chave e refutam com segurança quando o perfil
claramente não é daquela ordem, mas não afirmam a classe. Onde não podem
decidir, devolvem indeterminado.

Condições que a norma exige e o contrato não expressa (fendas verticais, COLE,
estrutura do B plânico) são objetos `Pendente`, que avaliam como
indeterminado. Não é dívida escondida: é a forma correta de representar uma
exigência que não se pode verificar, e o motivo aparece na saída.

### Resultado sobre o conjunto curado (94 perfis, 5ª edição, 2026-10-15)

```
concordância no 1º nível      :  50  (53,2%)
não conclusivos               :  44
divergentes a investigar      :   0
classes fora do conjunto alcançável: 0   (nas duas edições)

# estratificado pelo campo CURADORIA (python -m nucleo.avaliacao)
sem alteração        (32 perfis) → 22 concordam + 10 indeterminados que contêm o rótulo → contenção 32/32
com correção         (62 perfis) → 28 concordam + 33 indeterminados que contêm o rótulo
                                   + 1 com rótulo 'unknown' na origem → contenção 61/61 rotulados
```

✅ **As violações de contenção foram zeradas.** Em 2026-09-07 eram sete (quatro
na contagem final daquela data). Três delas eram perfis rotulados LATOSSOLO
com relação textural acima de 1,5, e a causa era do código: esse limite é do B
nítico, não do B latossólico, e o veto foi removido (ver a conferência dos
limiares abaixo). As demais caíram com os defeitos corrigidos depois. Hoje
`python -m nucleo.testes` confere a propriedade nas duas edições e passa.

⚠️ **Concordância aqui não é acurácia.** Sob a base da 5ª edição o rótulo e o
núcleo são da mesma edição, e a concordância mede implementação; sob a 6ª mede
diferença de norma somada à implementação. E 44 perfis saem não conclusivos
porque a triagem das oito ordens fora do recorte não decide. O número que
importa é o da contenção: **0 classes registradas fora do conjunto
alcançável** em 94 perfis.

### O caso-testemunha

`GeoTab_RN_007_Acu` é o perfil que o SmartSolos devolve como `unknown`, e cuja
ambiguidade a 6ª edição do SiBCS creditou ao sistema. Aqui:

```
? ATIVIDADE_ARGILA >= 27 cmolc/kg de argila em horizonte B textural
  nos primeiros 100 cm — 50 de 100 cm satisfazem (50%) — empate exato;
  a norma exige 'a maior parte' e não prevê desempate
```

Mesma indecisão, com o motivo dito. É a diferença entre `unknown` e um
diagnóstico — e é a razão de a agregação `"maior parte"` ser ponderada por
espessura dentro da seção de controle, e não uma contagem de horizontes.

### Defeitos que o conjunto curado pegou

Cada um virou teste de regressão em `nucleo/testes.py`, nomeando o perfil:

| Perfil | Defeito | Correção |
|---|---|---|
| `PE_032_Paudalho` | **a própria relação textural estava errada** — calculada de memória, não pela norma | reimplementada conforme Cap. 1 e a Tabela 1.1 (A inclusive AB, B inclusive BA e exclusive BC, seção de controle pelo dobro da espessura do A). Os três exemplos da norma são teste de regressão |
| `PE_031_Itambe` | `A/B` e `B/A` interpostos rompiam a adjacência | adjacência ignora transicionais |
| `PE_025_Barreiros` | 15 cm não descritos refutavam o Gleissolo | lacuna de descrição devolve indeterminado |
| `PE_039`, `PE_040` | A chernozêmico frouxo afirmava Chernossolo em Luvissolos | exige cor, C orgânico, estrutura, V% e espessura conjugados |
| `RN_043_Pedro_Avelino` | o sufixo `f` (plintita) era lido como horizonte plíntico e afirmava Plintossolo | veto do plíntico por espessura < 15 cm e por matriz que não é cor clara sem mosqueado claro (Cap. 2). ⚠️ *Corrigido em 2026-10-15*: esta linha descrevia como correção o critério improvisado "croma ≤ 2 e valor ≥ 5", que foi **removido** em 2026-09-17 |
| `RN_042_Santo_Antonio`, `PE_048_Goiana` | a condição (b) dos Plintossolos estava improvisada | as três formas da norma — matriz pálida, coloração variegada, mosqueado abundante (este último indeterminado: o contrato não tem a quantidade) |
| `RN_021_Ceara_Mirim` | símbolos em notação anterior a 1988 ficavam sem tipo; quantificador invertido na exclusão textural dos Gleissolos | traduzidos por `gramatica_sufixos.moderniza()`; exclusão só se **todos** os horizontes forem arenosos |
| `PE_025`, `PE_026` | a exigência dos 30 cm do glei, só da 6ª, vazava para a 5ª | predicado por edição |
| sintéticos | glei precedente preso ao horizonte imediato; A chernozêmico com estrutura fraca; plíntico dos Neossolos pela chave (40 cm) e não pelo Cap. 3 (150 cm); identificação aceita na falta do dado que a vetaria; requisitos (a) e (b) da Definição dos Argissolos ausentes | do 8º ao 12º defeito da monografia (§5.5) — nenhum dos 94 perfis cai nesses casos |

Lista completa e comentada: página `nucleo-simbolico-classolosbr-ns` do wiki.

## Conferência dos limiares contra o PDF (2026-09-07)

Todos os limiares numéricos foram cotejados com o texto da 6ª edição:

| Limiar | Situação |
|---|---|
| 27 cmolc/kg — Ta × Tb | ✅ literal |
| V ≥ 50% — saturação por bases alta (eutrófico) | ✅ literal |
| V ≥ 65% e C orgânico ≥ 6 g/kg — A chernozêmico | ✅ literal |
| 350 g/kg de argila — Nitossolos | ✅ literal |
| 300 g/kg nos 20 cm superficiais — Vertissolos | ✅ literal |
| Cerosidade "comum e moderado" — B nítico | ✅ literal (quantidade ≥ 2, grau ≥ 3) |
| Relação textural ≤ 1,5 | 🚨 **é do B nítico**, não do B latossólico — atribuição errada, corrigida |
| Limiar numérico para o B latossólico | 🚨 **não existe na 6ª edição** (os 1,80/1,70/1,50 são da 5ª, suprimidos) — veto removido |
| Fórmula da relação textural B/A | 🚨 **estava errada** — reimplementada, com os 3 exemplos da Tabela 1.1 como teste |
| Mudança textural abrupta | 🚨 **ramos invertidos** — a duplicação vale para A/E com < 200 g/kg; o incremento absoluto de 200, para ≥ 200 |
| Espessura do A chernozêmico | 🚨 **18 cm fixo estava permissivo** — são 25 cm se o solum ≥ 75 cm |

⚠️ Um quarto defeito apareceu ao corrigir os anteriores: `2Btn` e `2Btvn1`
começam com o dígito de descontinuidade litológica, e o código fatiava o
símbolo com `[:1]`. Quatro Planossolos perdiam a mudança textural abrupta por
isso. Todo acesso ao horizonte principal passa agora pela função `principal()`,
que usa o analisador de símbolos.

### Pendências do núcleo

- [ ] Níveis 2 a 4 (subordem, grande grupo, subgrupo) — só o 1º está feito.
- [x] Base da 5ª edição em paralelo, para a Camada de Versão. **Feito:**
      `chave5.py` é a base de produção, e `cli cotejar` / `cli edicoes`
      comparam as duas.
- [x] ~~Resolver com a Embrapa a leitura de "subjacente a"~~ — **tratado em
      2026-10-15**: a base da 6ª devolve indeterminado nos Argissolos **e** nos
      Luvissolos quando o B textural está nos primeiros 200 cm sem estar
      imediatamente abaixo do A ou E. A proposta de atualização do CE
      (Santos et al., 2026, Embrapa Solos, Documentos 257, p. 39) indica a
      leitura com adjacência, mas é proposta para teste, não norma: a
      indeterminação fica. A base de produção (5ª) não é afetada.
- [x] `RN_039_Riachuelo` e `RN_043_Pedro_Avelino` **deixaram de ser
      divergentes** (conferido em 2026-10-15, nas duas edições). Agora saem
      não conclusivos com o rótulo dentro do conjunto alcançável: RN_039 →
      LUVISSOLO, com PLANOSSOLO alcançável; RN_043 → LUVISSOLO, com
      CHERNOSSOLO alcançável. Concluir de fato ainda depende do B plânico e do
      horizonte plíntico propriamente dito, que a triagem não implementa.
- [ ] Sair da triagem nas oito ordens restantes. Na 5ª edição há 9 condições
      em `Pendente` (Organossolos 2, Neossolos 1, Vertissolos 3, Planossolos 1,
      Chernossolos 1, Nitossolos 1); ver `cli cobertura`.

## Decisões que valem saber antes de mexer

- **`raw/` é montado somente-leitura.** É fonte imutável pelo `CLAUDE.md` §1.
- **Nomes de coluna são saneados na Bronze.** O Spark recusa escrever Parquet
  com `(){};` no nome, e **55 das 275 colunas** do BDSolos têm parênteses
  (`Altitude (m)`, `Complexo Sortivo - Cálcio (cmolc/kg)`…). O mapa
  original → saneado vai no manifesto, então a rastreabilidade se preserva.
- **`Informações Complementares` aparece duas vezes no CSV.** Vira
  `informacoes_complementares` e `informacoes_complementares_2`. Um leitor
  baseado em dicionário perderia uma das duas em silêncio.
- **A chave de perfil é a tripla** `Código Trabalho` + `Código PA` + `Número PA`.
  `Código PA` sozinho dá 8.175 perfis, não 8.925 — perde 751 e mistura perfis
  distintos. (A tripla dá 8.925 chaves; na Prata ficam 8.923 perfis, depois de
  descartados os registros partidos — ver acima.)
- **A validação Bronze falha duro** se as contagens divergirem. Em Bronze,
  divergência quase sempre é erro de parsing (separador, quote, multiLine),
  não fonte nova.
- 🚨 **Coordenada sem hemisfério vira NULL, não positiva.** O BDSolos guarda
  latitude/longitude em graus-minutos-segundos separados, e **2.116 linhas têm
  grau de longitude sem hemisfério**. Assumir sinal positivo por omissão daria,
  para o Brasil, coordenada no hemisfério errado com aparência válida — foram
  **676 perfis** afetados no teste. Exigir hemisfério levou a taxa de
  coordenadas dentro do Brasil de **82,7% para 99,5%**.
- **O separador decimal do BDSolos é ponto, não vírgula** (verificado: zero
  vírgulas em todas as colunas numéricas amostradas). `cast` funciona direto.
- **Perfil não usa `dropDuplicates`.** As colunas de perfil deveriam ser
  constantes entre as linhas do mesmo perfil, mas **13 perfis divergem**. Como
  `dropDuplicates` não garante qual linha sobrevive, a escolha é feita por
  `row_number()` sobre o hash da linha — determinístico entre execuções.

## Integração do Inferidor ao fluxo (1º nível, 5ª edição) — 2026-10-18

> Consolidada a partir de uma cópia experimental isolada do projeto (rodadas v1, v2 e auditoria v3, 2026-10-18). Registro completo em `experimento_integracao/` (comece por `experimento_integracao/auditoria-v3-2026-10-18/relatorio/08-encerramento-da-etapa.md`, que prevalece sobre formulações anteriores).

`integracao/` coordena os seis componentes num fluxo único (`integracao.fluxo.executar`, comando `python -m integracao.cli executar PERFIL.json --variante A|B|C`):

1. validação e cópia da entrada (o original nunca é alterado);
2. Sentinela — sinaliza, não decide;
3. Núcleo, **resposta observacional** — antes de qualquer inferência e invariante a ela;
4. Camada de Versão — 5ª × 6ª, com categorias de divergência (edições anteriores à 5ª nunca excluídas);
5. Inferidor — só em horizonte sem símbolo, B sem sufixo de tipo ou símbolo antigo de leituras discordantes; propõe **símbolos** (rede ou árvores, mesma interface) ou se abstém, com motivo;
6. Núcleo, **cenários condicionais** — até 8 por perfil; a árvore de prova marca símbolo inferido, modelo, confiança e cenário; cenário vetado pelo dado ou fora do alcançável observacional é rejeitado; robustez só com enumeração completa;
7. conflitos anotado × proposto — hipóteses de anotação, que não alteram símbolo nem classe;
8. Explicador — hipóteses numéricas e de anotação em listas separadas, todas verificadas por reexecução; correção de anotação é avaliada à parte do preenchimento compatível;
9. Avaliador Parcial — próxima determinação sobre a resposta observacional.

**Correções do núcleo C1–C5** (`nucleo/avaliador.py`, interruptor `CORRECOES_INTEGRACAO`; desligado = comportamento anterior): símbolo ausente por supervalorização sobre `nucleo/dados/catalogo_simbolo_ausente.json` (C1); truncamento de leituras vira indeterminado (C2); pendentes nas agregações por tipo (C3) e, para B sem tipo, nos predicados derivados (C4); seletor "B diagnóstico" no contexto do perfil (C5). ⚠️ **Não implementado:** proteção estrutural para veto pendente nos predicados derivados — hoje tratada predicado a predicado, sem defeito demonstrado.

```bash
python -m integracao.testes                 # 83 verificações
python -m integracao.modelos treinar        # artefatos (determinístico; mesma configuração de inferidor.selecao)
python -m integracao.experimento rodar E1   # E1, E2, E3, E3b, E4
python -m integracao.experimento agregar
```

**Resultado (exploratório, dados já examinados).** A integração preservou a resposta observacional e apresentou consistência nos cenários examinados. A inferência de símbolos ampliou a resolução condicional, com erros adicionais (E1: rede 132 resoluções, 112 concordantes, 20 discordantes; árvores 121, 109, 12). Não foi demonstrada vantagem específica da rede sobre as árvores (+0,008 por perfil, IC [−0,035; +0,063]). As concordâncias de E1 medem recuperação da classe que o núcleo deriva dos símbolos originais antes da remoção, não correção pedológica independente; houve confiança ≈ 0,75 em símbolos errados. Calibração e validação independente são necessárias antes de uso automático.

## Pendências

- [ ] Conferir a tag `apache/airflow:2.10.5-python3.11` e subir se houver
      versão mais recente estável.
- [x] DAG da Prata (tipagem + rejeições + MERGE em Delta). **Escrito**:
      `prata_transforma_bdsolos.py` faz MERGE de `perfis` por `perfil_id`,
      overwrite de `horizontes` e rejeições em Parquet com motivo.
- [ ] **Subir a stack e executar Bronze e Prata no Spark.** Nenhum DAG rodou
      ainda: a Bronze foi validada simulando a lógica em pandas (log de
      2026-08-24), e a Prata e a task `sinalizar_simbolos`, por simulação em
      Python. Em 2026-10-15 o Docker Desktop nem estava em execução.
- [ ] DAG da camada Ouro, ligando o núcleo simbólico ao pipeline. Não existe.
- [ ] Definir a modelagem definitiva de `ouro.perfis_classificados` — a atual
      é mínima, só para o pipeline ter destino.
- [ ] `monitoring/prometheus.yml` não existe ainda; o profile `monitoring`
      só sobe depois que ele for criado.
