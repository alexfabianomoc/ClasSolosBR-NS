# Definições operacionais (aplicadas por perfil, nunca por cenário)

Implementadas em `reconciliacao/reconcilia.py` (função `eventos`), que relê os registros por
perfil gravados pelo experimento; nenhuma métrica soma cenários como se fossem perfis.

| Termo | Definição operacional | Campo em `perfis.csv` |
|---|---|---|
| **Resposta observacional** | saída do núcleo corrigido sobre os dados como estão (sem símbolo inferido); idêntica nas três variantes | `obs_classe`, `obs_conclusivo`, `obs_n_alc` |
| **Conclusiva** | classe atribuída e conjunto alcançável sem outra classe (`Resultado.conclusivo`) | — |
| **Classe de referência** | E1, E3, E3b: classe que o núcleo corrigido deriva dos **símbolos originais antes da remoção** (pode ser conclusiva ou não; ver `referencia_conclusiva`); E2, E4: **ORDEM registrada na ficha** (rótulo histórico, referência fraca). Nunca é preditor | `referencia`, `origem_referencia`, `referencia_conclusiva` |
| **Perfil acionado** | ao menos um horizonte com símbolo ausente, B sem sufixo de tipo ou leituras discordantes | `acionado`, `horiz_acionados` |
| **Abstenção** | horizonte acionado sem proposta (motivo registrado); perfil com abstenção total = todos os acionados se abstiveram ⇒ nenhum cenário | `horiz_abstencao`, `horiz_com_proposta` |
| **Cenário** | uma combinação de candidatos dos horizontes com proposta, reexecutada no núcleo (até 8 por perfil, em ordem do escore de ordenação) | `cenarios` |
| **Proposta rejeitada pelo núcleo** | cenário incompatível: o dado veta o tipo proposto, ou a saída sai do alcançável observacional | `cenarios_incompat`, `cenarios_fora_do_obs` |
| **Conjunto condicional do cenário** | conjunto alcançável da saída do núcleo naquele cenário | (v3: `cenarios_detalhe` no JSONL) |
| **Cenário 1** | o cenário **compatível** de maior escore de ordenação | `cond1_*` |
| **Classe condicional (única)** | a classe do cenário 1, quando ele é conclusivo | `cond1_classe` + `cond1_conclusivo` |
| **Agregação dos cenários** | (v3) união dos conjuntos alcançáveis dos cenários compatíveis; **robusta** = todos os cenários compatíveis conclusivos na mesma classe **e** enumeração completa (sem orçamento estourado) | `uniao_alc_cenarios_compat`, `robusta`, `avaliacao_cenarios_completa` |
| **Resultado não conclusivo** | observacional não conclusiva e (sem cenário compatível ou cenário 1 não conclusivo) | `melhor_origem = não conclusivo` |
| **Resolvido** | observacional **não** conclusiva **e** cenário 1 conclusivo | `resolvido` |
| **Concorda / discorda** | resolvido e classe condicional = / ≠ referência (só perfis com referência definida) | `concorda`, `discorda_com_ref` |
| **Referência presente / excluída** | presente no alcançável observacional (`ref_no_obs`); **excluída** = presente no observacional e ausente do conjunto do cenário 1 (ou do observacional, quando não há cenário) | `ref_no_cond1`, `ref_excluida` |
| **Melhor resposta disponível** | a observacional, se conclusiva; senão a classe condicional do cenário 1 (que continua sendo condicional); senão nenhuma | `melhor`, `melhor_origem` |
| **Certa / errada / resolvida** (comparações pareadas) | melhor resposta = referência / ≠ referência / existe; universo: perfis com referência definida | — |

## Relações que valem por construção (e foram conferidas nos dados)

* resolvidos = concordam + discordam + resolvidos sem referência;
* toda discordância de perfil com referência no alcançável observacional é também exclusão
  (classe conclusiva ≠ referência ⇒ referência fora do conjunto do cenário 1);
* exclusões = discordâncias com referência no observacional + cenários 1 não conclusivos que já não
  contêm a referência;
* "errada" na melhor resposta = discordantes condicionais + observacionais conclusivas erradas
  (estas são 0 em E1/E3/E3b e iguais nas três variantes).
