# Matriz de estado das correções C1–C5

Todas no mesmo interruptor `nucleo.avaliador.CORRECOES_INTEGRACAO` (A0 = desligado = núcleo
original). Os testes de regressão estão em `integracao/testes.py`
(`teste_correcoes`, `teste_auditoria_v3`); as verificações empíricas, em
`auditoria-v3-2026-10-18/casos_minimos/` e `resultados/verificacoes/`.

| | Defeito | Caminho corrigido | Escopo exato | Fora do escopo (e por quê) | Teste de regressão / caso mínimo |
|---|---|---|---|---|---|
| **C1** | símbolo ausente lido como "nenhum tipo" (vira falsidade) | `_variantes_de_leitura` → supervalorização sobre `nucleo/dados/catalogo_simbolo_ausente.json` (120 leituras) | horizontes com `SIMB_HORIZ` vazio; até 256 combinações (acima, toda regra I — declarado no detalhe) | leituras fora do catálogo: a garantia é **relativa ao catálogo** | `PE_001`, `Bt1` apagado |
| **C2** | combinações de leitura acima do orçamento descartadas em silêncio | `_avaliar_por_leitura` | qualquer regra avaliada sobre variantes truncadas sai I, com o total no detalhe | — | sintético com 32 combinações |
| **C3** | identificação pendente fora das agregações por tipo (`Compara`, `Booleano`) | `_com_pendentes` | **todo** tipo de pendência (B sem tipo, veto pendente, leituras discordantes) em condições com `Seletor(tipo=…)`; até 6 pendentes (acima, I) | `Existe` já tratava pendentes como I; predicados derivados não passam por aqui | `RN_007`, `Bt2 → B` |
| **C4** | predicado derivado só vê B afirmados (B sem tipo ignorado) | `_derivado_supervalorado` | predicados derivados em perfis com **B sem sufixo de tipo** (completamentos ∅, t, w, i, h; até 3 horizontes, acima I) | **identificações com veto pendente** (plíntico sem cor/espessura, B latossólico de espessura indeterminada, B nítico sem argila): não passam pela C4. Cada predicado derivado de 1º nível que lê tipos afirmados **também** consulta os pendentes explicitamente (`horizontes_indeterminados_do_tipo`, `b_indeterminados` — auditoria estática abaixo), e 1.226 preenchimentos compatíveis em 294 perfis não acharam violação (núcleo original e corrigido). Não há defeito demonstrado, mas a proteção é **predicado a predicado**, não estrutural | `BDSolos|598|5818|Perfil no 11`; caso mínimo do escopo: `A / Btf (sem cor) / Bt2` → requisitos dos Argissolos = I, e os dois preenchimentos da cor ficam no alcançável |
| **C5** (nova) | seletor "B diagnóstico" julgava cada horizonte isolado (perfil de um horizonte só) | `_selecionar` | `Existe(B diagnóstico)` nas regras dos Gleissolos (5ª e 6ª): agora usa as identificações afirmadas do perfil inteiro, como `tem_b_diagnostico` | — | caso mínimo `A / Bwg1 15-40 / Bw2 40-80 / C`: A0 GLEISSOLO nas duas edições, A LATOSSOLO |

## A frase ambígua do relatório anterior

"Identificações com veto pendente dentro dos predicados derivados continuam sem a correção C4"
descreve corretamente o **mecanismo** (a C4 não enumera mundos para vetos pendentes), mas foi
escrita sem verificação e sugeria um defeito que **não foi demonstrado**. A auditoria verificou:

1. **Estática** — dos 13 predicados derivados usados pelas chaves da 5ª e da 6ª, 9 leem
   identificações afirmadas; os 9 também consultam as pendentes. Os 4 restantes não leem tipo
   (mudança textural abrupta, textura arenosa) ou só consultam pendentes (A chernozêmico).
   Script e saída: `casos_minimos/` (reprodução no relatório de auditoria).
2. **Empírica** — `casos_minimos/contencao_veto_pendente.py`: todo perfil do BDSolos e do curado com
   veto pendente (294), quatro famílias de preenchimento compatível do dado ausente (limite inferior
   do horizonte aberto, cor da matriz, cor de mosqueado incompleto, argila ausente), 5ª e 6ª: 1.226
   preenchimentos, **0 violações** com e sem as correções.

## Por que os testes anteriores não pegaram a C5

* a ablação artificial reduz B a `B`, cuja pendência passa por `b_indeterminados` (contexto do
  perfil inteiro); o ramo defeituoso é o das identificações **afirmadas**;
* o efeito só aparece com B latossólico subdividido em horizontes de menos de 50 cm **e** glei em
  posição diagnóstica — combinação rara; nos registros reais o Gleissolo costuma ser refutado por
  outro conjunto (posição do glei);
* os testes de contenção comparam completamentos com o observado: se o observado e os
  completamentos erram do mesmo jeito (o mesmo seletor), a contenção não acusa — **contenção não
  é correção**.
