# Errata dos relatórios da rodada v2 (sem sobrescrevê-los)

Os arquivos de `experimento_integracao/relatorio/` e o texto entregue ao fim da sessão anterior
ficam como estavam; as correções valem a partir desta auditoria.

| Onde | Dizia | Correção |
|---|---|---|
| relatório v2, §4, §6; resposta final | "classe verdadeira", "símbolos verdadeiros" | **classe de referência**: a que o núcleo corrigido deriva dos **símbolos originais antes da remoção** (E1, E3, E3b). Ela herda as limitações do núcleo e não é classe independente; em 109 de 359 perfis de E1 ela nem é conclusiva. Em E2/E4, a referência é a **ORDEM registrada** (rótulo histórico) |
| relatório v2, §4 | concordância de 84,8% "contra a classe verdadeira" | 112/132 concordam com a **classe de referência**; as 112 são todas com referência conclusiva; das 20 discordâncias, 19 são com referência conclusiva e 1 com referência não conclusiva |
| resposta final ("completei de todas as formas compatíveis… 8.972 combinações") | enumeração completa | era **truncada** em 64 combinações por perfil (21 perfis afetados; 8.972 de 14.540), num catálogo de 4 sufixos sem a opção "continua sem tipo". Refeita sem limite: 31.600 combinações, 0 violações com C1–C5 (5 perfis violam no núcleo original) |
| relatório v2, §2 e matriz | C1–C4 apresentadas como cobrindo a garantia | a C4 cobre só o B sem tipo nos predicados derivados; o veto pendente é tratado predicado a predicado (sem defeito demonstrado); faltava a **C5** (seletor "B diagnóstico" fora de contexto), achada nesta auditoria |
| resposta final ("veto pendente… continuam sem a correção C4") | sugeria defeito pendente | descrição do mecanismo, não de defeito demonstrado — ver `02-matriz-C1-C5.md` |
| relatório v2, §4 ("condicional robusta") | 7 (rede) e 5 (árvores) robustas em E1, contadas como tal | a robustez era afirmada mesmo com cenários não avaliados (orçamento de 8). Na v3, com enumeração completa exigida, as robustas de E1 (contadas sobre todos os perfis) caem de 9 para 4 (rede) e de 6 para 4 (árvores); o relatório v2 dava 7 e 5 porque contava só os de observacional não conclusiva — números por perfil em `reconciliacao/v3/sobreposicao.md` |
| relatório v2 ("nenhuma classe condicional fora do conjunto alcançável") | podia ser lido como resultado do filtro | na v2, **nenhum cenário** saiu do alcançável antes do filtro (0 em todos os conjuntos); o filtro existe e na v1 removeu 17+ cenários |
| relatório v2, §4, Wilson | intervalos de Wilson por perfil | tratam perfis como independentes; em E1/E2 há dependência por levantamento — usar as diferenças pareadas com reamostragem de levantamentos |
| relatório v2, "rede não superou as árvores" | — | mantido, com a ressalva: ausência de superioridade **detectável** não é equivalência demonstrada (o IC de +0,008 vai de −0,035 a +0,063) |
