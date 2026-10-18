# Política de símbolos, orçamentos e o alcance das garantias

## 1. A emenda da política de símbolos (emenda 6)

* **Fonte da restrição:** decisão do usuário de 2026-10-15 (opção 1), registrada no log do wiki e
  no código (`nucleo/horizontes.py::_identificar_horizonte`, comentário da decisão; e
  `TIPOS_B_POR_SIMBOLO`): o `B` sem sufixo deixa pendentes **só os tipos de B** (textural,
  latossólico, incipiente, espódico, nítico). Glei, plíntico, concrecionário e vértico não ficam
  pendentes: o `B` os nega como `Bt` os nega.
* **Consequência para o Inferidor:** completar `B` com `g`, `c`, `f` ou `v` não é preencher o que
  falta — é contradizer o que está anotado. A emenda separa duas operações:
  * **complementação** (cenário condicional): só sufixos de tipo de B (`t w i h s`);
  * **correção de anotação** (hipótese do Explicador): substituição ou complementação com qualquer
    sufixo, em cópia do perfil, avaliada à parte e **sem** exigência de ficar no alcançável
    observacional, porque altera a premissa.
  O código confere: `integracao/inferidor.py::Inferidor.propor` (restrição só para o gatilho "B sem
  tipo") e `Inferidor.conflitos` (candidatos completos, usados só em `hipoteses_de_anotacao`).
* **Mesma regra para os dois modelos:** a política está na classe `Inferidor`, que embrulha
  qualquer `Estimador`; rede e árvores passam pelo mesmo código.
* **Quando foi feita:** **depois** de ver resultados parciais da rodada v1 (registrado na emenda 6
  e em `resultados/etapa1_integracao/v1_interrompida/LEIA-ME.md`). A v1 parcial está preservada.
* **Efeito medido** (`reconciliacao/v1_x_v2_emenda6.txt`, perfis em comum):
  E1 (251 perfis): rede 97→95 resolvidos, 85→85 concordantes, 12→10 discordantes, 18→0 cenários
  fora do alcançável; árvores 85→84, 75→76, 10→8, 9→0. E2, E3, E4: nenhuma mudança nos resolvidos,
  só os cenários fora do alcançável zerados (14→0, 2→0; 6→0, 1→0). O efeito é pequeno, simétrico
  entre os modelos e na direção da solidez; não há exclusão que favoreça a rede.

## 2. Orçamentos: onde a avaliação pode ficar incompleta e como isso aparece

| Orçamento | Onde | Ao estourar | Declarado na saída? |
|---|---|---|---|
| 16 combinações de leitura (256 com símbolo ausente) | `avaliador._variantes_de_leitura` (C2) | toda regra afetada sai I | sim, no detalhe da derivação |
| 6 pendentes por agregação | `avaliador._com_pendentes` (C3) | I | sim, no detalhe |
| 3 horizontes B sem tipo por predicado derivado | `avaliador._derivado_supervalorado` (C4) | I | sim, no detalhe |
| 6 horizontes inferidos por perfil | `fluxo.cenarios` | os excedentes ficam com o símbolo anotado | sim: `horizontes_nao_inferidos_por_orcamento`, `aviso_orcamento` |
| 8 cenários por perfil | `fluxo.cenarios` | os de menor escore não são avaliados | **v2: só `combinacoes_possiveis` × `cenarios_avaliados`, e a robustez era afirmada assim mesmo — corrigido na v3** (`avaliacao_completa`, `aviso_orcamento`; robustez só com enumeração completa) |
| 30 hipóteses de anotação | `fluxo.hipoteses_de_anotacao` | as demais não são testadas | não explicitamente (limitação registrada) |
| 64 combinações por perfil | `diagnostico/contencao_preenchimento.py` (v2) | **truncamento silencioso** em 21 perfis | **não** — ver §3 |

## 3. As "8.972 combinações" da rodada v2

* **Perfis:** os 373 de E1 (BDSolos, levantamentos de teste) e os 67 de E3 (curado).
* **Símbolos removidos:** em cada horizonte B com sufixo de tipo de B e sem g/f/c/v/m, o símbolo
  foi reduzido a prefixo + `B` (`2Bt2` → `2B`); 1 a 5 horizontes por perfil.
* **Catálogo das alternativas:** `t`, `w`, `i`, `h` por horizonte (não incluía o próprio `B` sem
  tipo, nem `s`, equivalente a `h` no 1º nível).
* **Como se chegou a 8.972:** 4^k combinações por perfil, **cortadas nas 64 primeiras**
  (`list(product(...))[:64]`): E1 7.540 de 12.148 possíveis, E3 1.432 de 2.392. **21 perfis (20 de
  E1 e 1 de E3), com 4 ou 5 horizontes mascarados, foram truncados em silêncio.**
* **Propriedade verificada:** alcançável(preenchido) ⊆ alcançável(mascarado), só na 5ª edição.
* **O que a frase "de todas as formas compatíveis" deveria dizer:** enumeração parcial, num
  catálogo finito de quatro sufixos, nos perfis de E1 e E3. Era incorreta.
* **Refeito na auditoria** (`casos_minimos/contencao_preenchimento_exaustiva.py`): catálogo
  {∅, t, w, i, h}, 5^k combinações **sem limite** — resultado em §3.1.

### 3.1 Resultado da enumeração exaustiva

| | Núcleo original (A0) | Corrigido (C1–C5) |
|---|---|---|
| E1 — 373 perfis, **26.045** combinações (5^k, sem limite) | **5 perfis** com saída fora do alcançável mascarado (`BDSolos|643|7218`, `598|5818`, `598|5808`, `763|11253`, `779|12103`) | **0** |
| E3 — 67 perfis, **5.555** combinações | 0 | **0** |
| Tempo | 825 s | 2.618 s |

Total: 31.600 combinações, enumeradas sem truncamento, amostragem ou interrupção. A
propriedade foi conferida só na 5ª edição. O quinto perfil do A0, `BDSolos|643|7218` (combinação
`∅t`), não apareceu na v2 porque exige que um dos horizontes **permaneça sem tipo**, opção que o
catálogo truncado não tinha.

## 4. Três tipos de afirmação — o que cada teste sustenta

| | Enumeração exaustiva num catálogo finito | Teste em perfis determinados | Garantia geral |
|---|---|---|---|
| Contenção sob preenchimento do B sem tipo | sim, para {∅,t,w,i,h} em E1+E3 (§3.1) | sim | **não**: depende do catálogo e dos perfis; as regras são finitas, mas não há prova formal |
| Contenção sob símbolo ausente (C1) | relativa às 120 leituras do catálogo | apagamento no curado (168 casos) | não |
| Contenção sob veto pendente | — | 1.226 preenchimentos em 294 perfis | não |
| Preservação observacional | — | 1.084 perfis × 3 variantes (v2 e v3) | por construção do fluxo (calculada antes da inferência, sobre cópia), conferida por SHA |
