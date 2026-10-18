# 4. Resultados (gerado por `gera_tabelas.py` a partir de `resumo.json`)

## E1 — BDSolos-teste, ablação artificial (B com tipo → B)

Perfis: **373** (35 grupos — levantamentos no BDSolos, perfis no curado); falhas de execução A/B/C: {'A': 0, 'B': 0, 'C': 0}; verificações finais violadas: {'A': 0, 'B': 0, 'C': 0}.
Invariância da resposta observacional A = B = C: **373/373 (100.0%)**; da Camada de Versão: 373/373 (100.0%).
Efeito das correções (A0 × A, resposta observacional diferente): 26 perfis.
Classe com os símbolos verdadeiros dentro do alcançável observacional: A 359/359 (100.0%); A0 355/359 (98.9%).

| | A (sem inferência) | B (rede) | C (árvores) |
|---|---|---|---|
| horizontes acionados | 658 | 658 | 658 |
| horizontes com proposta | — | 407/658 (61.9%) | 353/658 (53.6%) |
| abstenções (motivo: n) | — | o candidato principal não informa o tipo do horizonte: 226; confiança de tipo: 22; nenhum candidato bem-formado pela gramática do Sentinela: 3 | o candidato principal não informa o tipo do horizonte: 292; confiança de tipo: 13 |
| candidatos bem-formados | — | 1935/1974 (98.0%) | 1927/1974 (97.6%) |
| cenários compatíveis | — | 1335/1335 (100.0%) | 1149/1149 (100.0%) |
| incompatibilidades | — | — | — |
| **violações de contenção** | 0 | 0 | 0 |
| observacional não conclusiva | 371 | 371 | 371 |
| → condicional conclusiva (cenário 1) | 0/371 (0.0%) | 132/371 (35.6%) | 121/371 (32.6%) |
| → condicional robusta (todos os cenários) | 0/371 (0.0%) | 7/371 (1.9%) | 5/371 (1.3%) |
| condicionais concordantes / discordantes | 0 / 0 | 112 / 20 | 109 / 12 |
| robustas concordantes | 0 | 7 | 5 |
| referência no alcançável (cenário 1 ou obs.) | 359 | 333 | 344 |
| conflitos sinalizados (horizontes) | 0 | 107 | 143 |
| divergentes no Explicador (perfis) | 23 | 23 | 23 |
| hipóteses de anotação geradas / verificadas | 0 / 0 | 111 / 2 | 105 / 1 |
| perfis com hipótese de anotação verificada | 0 | 2 | 1 |
| tempo por perfil: média / mediana / p95 (s) | 1.06 / 0.20 / 4.97 | 1.54 / 0.49 / 6.25 | 1.87 / 0.77 / 6.86 |
| cenários avaliados | 0 | 1335 | 1149 |

Referência das concordâncias: classe com os símbolos verdadeiros.

Comparações pareadas sobre a **melhor resposta disponível** (observacional se conclusiva; senão a condicional do cenário 1, que continua sendo condicional). Diferença por perfil, IC 95% por reamostragem de grupos, discordantes (a favor da 1ª / da 2ª) e McNemar exato:

| comparação | medida | n | 1ª | 2ª | dif./perfil | IC 95% | discordantes | p |
|---|---|---|---|---|---|---|---|---|
| B × A | certa | 359 | 114 | 2 | +0.312 | [+0.254; +0.358] | 112/0 | 3.85e-34 |
| B × A | errada | 359 | 20 | 0 | +0.056 | [+0.030; +0.081] | 20/0 | 1.91e-06 |
| B × A | resolvida | 359 | 134 | 2 | +0.368 | [+0.308; +0.413] | 132/0 | 3.67e-40 |
| C × A | certa | 359 | 111 | 2 | +0.304 | [+0.221; +0.368] | 109/0 | 3.08e-33 |
| C × A | errada | 359 | 12 | 0 | +0.033 | [+0.013; +0.061] | 12/0 | 0.000488 |
| C × A | resolvida | 359 | 123 | 2 | +0.337 | [+0.259; +0.401] | 121/0 | 7.52e-37 |
| B × C | certa | 359 | 114 | 111 | +0.008 | [-0.035; +0.063] | 28/25 | 0.784 |
| B × C | errada | 359 | 20 | 12 | +0.022 | [-0.011; +0.046] | 14/6 | 0.115 |
| B × C | resolvida | 359 | 134 | 123 | +0.031 | [-0.026; +0.089] | 33/22 | 0.177 |

## E2 — BDSolos-teste, incompletude natural

Perfis: **483** (26 grupos — levantamentos no BDSolos, perfis no curado); falhas de execução A/B/C: {'A': 0, 'B': 0, 'C': 0}; verificações finais violadas: {'A': 0, 'B': 0, 'C': 0}.
Invariância da resposta observacional A = B = C: **483/483 (100.0%)**; da Camada de Versão: 483/483 (100.0%).
Efeito das correções (A0 × A, resposta observacional diferente): 91 perfis.

| | A (sem inferência) | B (rede) | C (árvores) |
|---|---|---|---|
| horizontes acionados | 1176 | 1176 | 1176 |
| horizontes com proposta | — | 461/1176 (39.2%) | 382/1176 (32.5%) |
| abstenções (motivo: n) | — | o candidato principal não informa o tipo do horizonte: 671; confiança de tipo: 36; nenhum candidato bem-formado pela gramática do Sentinela: 8 | o candidato principal não informa o tipo do horizonte: 768; confiança de tipo: 19; nenhum candidato bem-formado pela gramática do Sentinela: 7 |
| candidatos bem-formados | — | 3407/3512 (97.0%) | 3381/3512 (96.3%) |
| cenários compatíveis | — | 1480/1484 (99.7%) | 1231/1232 (99.9%) |
| incompatibilidades | — | Btw: 4 | Btw: 1 |
| **violações de contenção** | 0 | 0 | 0 |
| observacional não conclusiva | 473 | 473 | 473 |
| → condicional conclusiva (cenário 1) | 0/473 (0.0%) | 80/473 (16.9%) | 52/473 (11.0%) |
| → condicional robusta (todos os cenários) | 0/473 (0.0%) | 0/473 (0.0%) | 0/473 (0.0%) |
| condicionais concordantes / discordantes | 0 / 0 | 34 / 46 | 17 / 35 |
| robustas concordantes | 0 | 0 | 0 |
| referência no alcançável (cenário 1 ou obs.) | 447 | 383 | 392 |
| conflitos sinalizados (horizontes) | 0 | 86 | 98 |
| divergentes no Explicador (perfis) | 35 | 35 | 35 |
| hipóteses de anotação geradas / verificadas | 0 / 0 | 95 / 1 | 86 / 0 |
| perfis com hipótese de anotação verificada | 0 | 1 | 0 |
| tempo por perfil: média / mediana / p95 (s) | 1.55 / 0.36 / 6.54 | 2.69 / 1.15 / 8.83 | 2.88 / 1.28 / 10.04 |
| cenários avaliados | 0 | 1484 | 1232 |

Referência das concordâncias: ORDEM registrada (referência fraca).

Comparações pareadas sobre a **melhor resposta disponível** (observacional se conclusiva; senão a condicional do cenário 1, que continua sendo condicional). Diferença por perfil, IC 95% por reamostragem de grupos, discordantes (a favor da 1ª / da 2ª) e McNemar exato:

| comparação | medida | n | 1ª | 2ª | dif./perfil | IC 95% | discordantes | p |
|---|---|---|---|---|---|---|---|---|
| B × A | certa | 482 | 42 | 8 | +0.071 | [+0.048; +0.092] | 34/0 | 1.16e-10 |
| B × A | errada | 482 | 48 | 2 | +0.095 | [+0.047; +0.162] | 46/0 | 2.84e-14 |
| B × A | resolvida | 482 | 90 | 10 | +0.166 | [+0.114; +0.230] | 80/0 | 1.65e-24 |
| C × A | certa | 482 | 25 | 8 | +0.035 | [+0.016; +0.060] | 17/0 | 1.53e-05 |
| C × A | errada | 482 | 37 | 2 | +0.073 | [+0.020; +0.143] | 35/0 | 5.82e-11 |
| C × A | resolvida | 482 | 62 | 10 | +0.108 | [+0.046; +0.187] | 52/0 | 4.44e-16 |
| B × C | certa | 482 | 42 | 25 | +0.035 | [+0.015; +0.053] | 20/3 | 0.000488 |
| B × C | errada | 482 | 48 | 37 | +0.023 | [+0.011; +0.035] | 19/8 | 0.0522 |
| B × C | resolvida | 482 | 90 | 62 | +0.058 | [+0.032; +0.084] | 38/10 | 6.17e-05 |

## E3 — curado, ablação artificial

Perfis: **67** (67 grupos — levantamentos no BDSolos, perfis no curado); falhas de execução A/B/C: {'A': 0, 'B': 0, 'C': 0}; verificações finais violadas: {'A': 0, 'B': 0, 'C': 0}.
Invariância da resposta observacional A = B = C: **67/67 (100.0%)**; da Camada de Versão: 67/67 (100.0%).
Efeito das correções (A0 × A, resposta observacional diferente): 1 perfis.
Classe com os símbolos verdadeiros dentro do alcançável observacional: A 66/66 (100.0%); A0 66/66 (100.0%).

| | A (sem inferência) | B (rede) | C (árvores) |
|---|---|---|---|
| horizontes acionados | 124 | 124 | 124 |
| horizontes com proposta | — | 75/124 (60.5%) | 84/124 (67.7%) |
| abstenções (motivo: n) | — | o candidato principal não informa o tipo do horizonte: 47; confiança de tipo: 1; nenhum candidato bem-formado pela gramática do Sentinela: 1 | o candidato principal não informa o tipo do horizonte: 38; confiança de tipo: 1; nenhum candidato bem-formado pela gramática do Sentinela: 1 |
| candidatos bem-formados | — | 364/372 (97.8%) | 355/372 (95.4%) |
| cenários compatíveis | — | 232/232 (100.0%) | 284/284 (100.0%) |
| incompatibilidades | — | — | — |
| **violações de contenção** | 0 | 0 | 0 |
| observacional não conclusiva | 67 | 67 | 67 |
| → condicional conclusiva (cenário 1) | 0/67 (0.0%) | 25/67 (37.3%) | 19/67 (28.4%) |
| → condicional robusta (todos os cenários) | 0/67 (0.0%) | 3/67 (4.5%) | 0/67 (0.0%) |
| condicionais concordantes / discordantes | 0 / 0 | 22 / 3 | 17 / 2 |
| robustas concordantes | 0 | 3 | 0 |
| referência no alcançável (cenário 1 ou obs.) | 66 | 62 | 62 |
| conflitos sinalizados (horizontes) | 0 | 41 | 50 |
| divergentes no Explicador (perfis) | 0 | 0 | 0 |
| hipóteses de anotação geradas / verificadas | 0 / 0 | 0 / 0 | 0 / 0 |
| perfis com hipótese de anotação verificada | 0 | 0 | 0 |
| tempo por perfil: média / mediana / p95 (s) | 24.69 / 8.71 / 95.52 | 1.63 / 0.74 / 5.69 | 2.15 / 1.18 / 6.18 |
| cenários avaliados | 0 | 232 | 284 |

Referência das concordâncias: classe com os símbolos verdadeiros.

Comparações pareadas sobre a **melhor resposta disponível** (observacional se conclusiva; senão a condicional do cenário 1, que continua sendo condicional). Diferença por perfil, IC 95% por reamostragem de grupos, discordantes (a favor da 1ª / da 2ª) e McNemar exato:

| comparação | medida | n | 1ª | 2ª | dif./perfil | IC 95% | discordantes | p |
|---|---|---|---|---|---|---|---|---|
| B × A | certa | 66 | 22 | 0 | +0.333 | [+0.212; +0.439] | 22/0 | 4.77e-07 |
| B × A | errada | 66 | 3 | 0 | +0.045 | [+0.000; +0.106] | 3/0 | 0.25 |
| B × A | resolvida | 66 | 25 | 0 | +0.379 | [+0.258; +0.500] | 25/0 | 5.96e-08 |
| C × A | certa | 66 | 17 | 0 | +0.258 | [+0.152; +0.364] | 17/0 | 1.53e-05 |
| C × A | errada | 66 | 2 | 0 | +0.030 | [+0.000; +0.076] | 2/0 | 0.5 |
| C × A | resolvida | 66 | 19 | 0 | +0.288 | [+0.182; +0.394] | 19/0 | 3.81e-06 |
| B × C | certa | 66 | 22 | 17 | +0.076 | [-0.015; +0.167] | 8/3 | 0.227 |
| B × C | errada | 66 | 3 | 2 | +0.015 | [-0.045; +0.076] | 3/2 | 1 |
| B × C | resolvida | 66 | 25 | 19 | +0.091 | [+0.000; +0.182] | 9/3 | 0.146 |

## E3b — curado, símbolo do 1º B apagado

Perfis: **67** (67 grupos — levantamentos no BDSolos, perfis no curado); falhas de execução A/B/C: {'A': 0, 'B': 0, 'C': 0}; verificações finais violadas: {'A': 0, 'B': 0, 'C': 0}.
Invariância da resposta observacional A = B = C: **67/67 (100.0%)**; da Camada de Versão: 67/67 (100.0%).
Efeito das correções (A0 × A, resposta observacional diferente): 67 perfis.
Classe com os símbolos verdadeiros dentro do alcançável observacional: A 66/66 (100.0%); A0 3/66 (4.5%).

| | A (sem inferência) | B (rede) | C (árvores) |
|---|---|---|---|
| horizontes acionados | 67 | 67 | 67 |
| horizontes com proposta | — | 52/67 (77.6%) | 50/67 (74.6%) |
| abstenções (motivo: n) | — | o candidato principal não informa o tipo do horizonte: 12; nenhum candidato bem-formado pela gramática do Sentinela: 3 | o candidato principal não informa o tipo do horizonte: 13; confiança de tipo: 2; nenhum candidato bem-formado pela gramática do Sentinela: 2 |
| candidatos bem-formados | — | 173/201 (86.1%) | 151/201 (75.1%) |
| cenários compatíveis | — | 137/139 (98.6%) | 110/110 (100.0%) |
| incompatibilidades | — | Af: 2 | — |
| **violações de contenção** | 0 | 0 | 0 |
| observacional não conclusiva | 67 | 67 | 67 |
| → condicional conclusiva (cenário 1) | 0/67 (0.0%) | 30/67 (44.8%) | 25/67 (37.3%) |
| → condicional robusta (todos os cenários) | 0/67 (0.0%) | 5/67 (7.5%) | 8/67 (11.9%) |
| condicionais concordantes / discordantes | 0 / 0 | 26 / 4 | 22 / 3 |
| robustas concordantes | 0 | 4 | 8 |
| referência no alcançável (cenário 1 ou obs.) | 66 | 58 | 60 |
| conflitos sinalizados (horizontes) | 0 | 50 | 56 |
| divergentes no Explicador (perfis) | 0 | 0 | 0 |
| hipóteses de anotação geradas / verificadas | 0 / 0 | 0 / 0 | 0 / 0 |
| perfis com hipótese de anotação verificada | 0 | 0 | 0 |
| tempo por perfil: média / mediana / p95 (s) | 9.29 / 8.38 / 15.69 | 9.65 / 8.65 / 18.60 | 9.78 / 8.80 / 18.07 |
| cenários avaliados | 0 | 139 | 110 |

Referência das concordâncias: classe com os símbolos verdadeiros.

Comparações pareadas sobre a **melhor resposta disponível** (observacional se conclusiva; senão a condicional do cenário 1, que continua sendo condicional). Diferença por perfil, IC 95% por reamostragem de grupos, discordantes (a favor da 1ª / da 2ª) e McNemar exato:

| comparação | medida | n | 1ª | 2ª | dif./perfil | IC 95% | discordantes | p |
|---|---|---|---|---|---|---|---|---|
| B × A | certa | 66 | 26 | 0 | +0.394 | [+0.273; +0.515] | 26/0 | 2.98e-08 |
| B × A | errada | 66 | 4 | 0 | +0.061 | [+0.015; +0.121] | 4/0 | 0.125 |
| B × A | resolvida | 66 | 30 | 0 | +0.455 | [+0.333; +0.576] | 30/0 | 1.86e-09 |
| C × A | certa | 66 | 22 | 0 | +0.333 | [+0.227; +0.455] | 22/0 | 4.77e-07 |
| C × A | errada | 66 | 3 | 0 | +0.045 | [+0.000; +0.106] | 3/0 | 0.25 |
| C × A | resolvida | 66 | 25 | 0 | +0.379 | [+0.258; +0.500] | 25/0 | 5.96e-08 |
| B × C | certa | 66 | 26 | 22 | +0.061 | [-0.030; +0.167] | 8/4 | 0.388 |
| B × C | errada | 66 | 4 | 3 | +0.015 | [-0.045; +0.076] | 3/2 | 1 |
| B × C | resolvida | 66 | 30 | 25 | +0.076 | [-0.030; +0.182] | 9/4 | 0.267 |

## E4 — fichas originais pré-curadoria

Perfis: **94** (94 grupos — levantamentos no BDSolos, perfis no curado); falhas de execução A/B/C: {'A': 0, 'B': 0, 'C': 0}; verificações finais violadas: {'A': 0, 'B': 0, 'C': 0}.
Invariância da resposta observacional A = B = C: **94/94 (100.0%)**; da Camada de Versão: 94/94 (100.0%).
Efeito das correções (A0 × A, resposta observacional diferente): 1 perfis.

| | A (sem inferência) | B (rede) | C (árvores) |
|---|---|---|---|
| horizontes acionados | 18 | 18 | 18 |
| horizontes com proposta | — | 7/18 (38.9%) | 11/18 (61.1%) |
| abstenções (motivo: n) | — | o candidato principal não informa o tipo do horizonte: 10; confiança de tipo: 1 | o candidato principal não informa o tipo do horizonte: 7 |
| candidatos bem-formados | — | 54/54 (100.0%) | 52/54 (96.3%) |
| cenários compatíveis | — | 23/23 (100.0%) | 38/38 (100.0%) |
| incompatibilidades | — | — | — |
| **violações de contenção** | 0 | 0 | 0 |
| observacional não conclusiva | 42 | 42 | 42 |
| → condicional conclusiva (cenário 1) | 0/42 (0.0%) | 0/42 (0.0%) | 0/42 (0.0%) |
| → condicional robusta (todos os cenários) | 0/42 (0.0%) | 0/42 (0.0%) | 0/42 (0.0%) |
| condicionais concordantes / discordantes | 0 / 0 | 0 / 0 | 0 / 0 |
| robustas concordantes | 0 | 0 | 0 |
| referência no alcançável (cenário 1 ou obs.) | 85 | 84 | 85 |
| conflitos sinalizados (horizontes) | 0 | 61 | 69 |
| divergentes no Explicador (perfis) | 8 | 8 | 8 |
| hipóteses de anotação geradas / verificadas | 0 / 0 | 16 / 2 | 11 / 0 |
| perfis com hipótese de anotação verificada | 0 | 1 | 0 |
| tempo por perfil: média / mediana / p95 (s) | 5.40 / 0.22 / 13.31 | 0.99 / 0.13 / 5.07 | 1.39 / 0.37 / 5.92 |
| cenários avaliados | 0 | 23 | 38 |

Referência das concordâncias: ORDEM registrada (referência fraca).

Comparações pareadas sobre a **melhor resposta disponível** (observacional se conclusiva; senão a condicional do cenário 1, que continua sendo condicional). Diferença por perfil, IC 95% por reamostragem de grupos, discordantes (a favor da 1ª / da 2ª) e McNemar exato:

| comparação | medida | n | 1ª | 2ª | dif./perfil | IC 95% | discordantes | p |
|---|---|---|---|---|---|---|---|---|
| B × A | certa | 94 | 47 | 47 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| B × A | errada | 94 | 5 | 5 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| B × A | resolvida | 94 | 52 | 52 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| C × A | certa | 94 | 47 | 47 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| C × A | errada | 94 | 5 | 5 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| C × A | resolvida | 94 | 52 | 52 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| B × C | certa | 94 | 47 | 47 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| B × C | errada | 94 | 5 | 5 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |
| B × C | resolvida | 94 | 52 | 52 | +0.000 | [+0.000; +0.000] | 0/0 | 1 |

**Conflitos e Explicador nas fichas originais (referência: trocas substantivas de símbolo da curadoria):**

| | B (rede) | C (árvores) |
|---|---|---|
| trocas sinalizadas pelo conflito | 14/50 (28.0%) | 6/50 (12.0%) |
| falso alerta (conflito sem troca) | 36/362 (9.9%) | 51/362 (14.1%) |
| horizontes acionados com troca: n / abstenções / assinatura = curada | 18 / 11 / 3 | 18 / 7 / 6 |
| casos de referência para Acerto@k (divergentes com troca) | 6 | 6 |
| Acerto@1 / @3 (horizonte e assinatura) | 0 / 1 | 0 / 0 |
| Acerto@1 / @3 (só horizonte) | 1 / 1 | 0 / 0 |

Hipóteses numéricas idênticas entre A, B e C: 94/94 perfis.
