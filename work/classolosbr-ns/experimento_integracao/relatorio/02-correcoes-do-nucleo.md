# 2. Defeitos que inviabilizavam invariantes — corrigidos só na cópia

Todos afetam a mesma garantia: **ausência de informação não pode virar falsidade**, e o
conjunto alcançável tem de conter a classe que qualquer completamento compatível dos dados
produziria. Sem essa garantia, a integração do Inferidor fica sem chão: um símbolo inferido
poderia "descobrir" uma classe que a resposta observacional já tinha excluído, e a classe
condicional deixaria de ser um refinamento da observacional.

Todas as correções ficam atrás de `nucleo.avaliador.CORRECOES_INTEGRACAO` (padrão `True` na
cópia). Com `False`, o núcleo é byte a byte o comportamento original — é a variante **A0** do
experimento, que isola o efeito das correções do efeito da integração.

| | Defeito (evidência) | Correção | Teste de regressão |
|---|---|---|---|
| **C1** | Símbolo ausente (`SIMB_HORIZ` vazio) não recebia tipo nenhum, e "existe B textural", a adjacência ao A e o gate dos Neossolos passavam a **falso**. Apagar o símbolo de um B no conjunto curado tirava a classe derivada do alcançável em **92 de 168** apagamentos (`resultados/correcoes/contencao-apagamento-A0.txt`); ex.: `PE_001` (`Bt1` apagado) → "nenhuma classe do recorte se aplica" | supervalorização sobre um **catálogo** de 120 leituras (assinaturas observadas no BDSolos: principal válido × sufixos que a base lê, completadas pelos tipos de B e pares), orçamento de 256 combinações | `teste_correcoes` (PE_001) |
| **C2** | Acima de `MAX_VARIANTES` (16) combinações de leitura, as excedentes eram **descartadas** e um valor unânime entre as avaliadas valia para todas. Incidência medida: 1 perfil do BDSolos, 0 do curado | com truncamento, a regra sai indeterminada | `teste_correcoes` (sintético, 32 combinações) |
| **C3** | Agregações por tipo ("a maior parte do B textural", "todos", "qualquer") ignoravam horizontes de **identificação pendente**, como se se soubesse que não eram do tipo. `RN_007`: `Bt2` → `B` dava LUVISSOLO e tirava ARGISSOLO do alcançável; `RN_043`: `Btfn2` → `B` trocava LUVISSOLO por ARGISSOLO | supervalorização sobre os subconjuntos dos pendentes (até 6; acima, indeterminado) | `teste_correcoes` (RN_007) |
| **C4** | Predicados **derivados** (ex.: `requisitos_argissolos_5ed`) só viam os B afirmados: com os B do topo pendentes, o "topo do B textural" passava a ser o `Btf` a 130 cm e o Argissolo era refutado, embora o completamento `Bt` o concluísse (`BDSolos|598|5818|Perfil no 11`, achado na rodada v1) | predicado avaliado no perfil e em cada completamento do B sem tipo por `t`, `w`, `i`, `h`, com supervalorização (até 3 horizontes; acima, indeterminado) | `teste_correcoes` (perfil do BDSolos) |

**O que não foi corrigido, e por quê.** O `B` sem sufixo deixa pendentes só os tipos de **B**
(decisão do usuário de 2026-10-15): ele nega glei, plíntico, concrecionário e vértico. Por isso
reduzir `2Btf` a `B` tira o Plintossolo do alcançável (`PE_048`) — não é defeito, é a
semântica decidida, e a corrupção artificial do experimento foi ajustada para não apagar esses
sufixos (emenda 1). Não se ampliou a interpretação normativa. Os predicados derivados também
podem ignorar identificações com **veto pendente** (dado que poderia vetar ausente) — a C4 cobre
só o B sem tipo, que é o domínio do Inferidor; o caso geral fica como limitação, vigiado pelos
testes empíricos de contenção abaixo.

## 2.1 Efeito das correções

Testes de contenção **independentes de modelo** (`experimento_integracao/diagnostico/`,
saídas em `resultados/correcoes/`):

| Teste | Núcleo original (A0) | Só C1+C2 | Corrigido (C1–C4) |
|---|---|---|---|
| Apagar ('') o símbolo de cada B do curado: classe derivada fora do alcançável | **92/168** | 0/168 | **0/168** |
| Reduzir cada B do curado a 'B': idem | 3/168 (PE_048, RN_007, RN_043) | 3/168 | **1/168** (PE_048 — perda do `f`, semântica decidida, não defeito) |
| Preencher os B mascarados de E1/E3 com todo produto de `t w i h` (8.972 completamentos): saída fora do alcançável mascarado | **4/373** perfis em E1, 0/67 em E3 | — | **0/373, 0/67** |
| `nucleo.testes` (suíte original, inclui os números do conjunto curado: 50/44/0, contenção nas duas edições, "5 dos 94") | passa | — | **passa** |

Os números históricos do conjunto curado que a suíte original confere não mudaram com C1–C4.
No experimento, a diferença A0 × A na resposta observacional aparece por conjunto em §4.
