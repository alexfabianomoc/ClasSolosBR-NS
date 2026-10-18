# Auditoria da integração ClasSolosBR-NS — versão 3 (2026-10-18)

> Nota da publicação: caminhos locais da estação de trabalho substituídos por marcadores (`<cópia experimental>`, `<projeto original>`); o restante do texto é o do registro original.

*Cópia experimental `<cópia experimental>`. Diretório desta auditoria:
`work/classolosbr-ns/experimento_integracao/auditoria-v3-2026-10-18/`. Nada foi levado à
monografia, ao artigo ou ao projeto original. A rodada v3 **não é confirmação independente**:
perfis, modelos e resultados já tinham sido examinados.*

Documentos: [02 — matriz C1–C5](02-matriz-C1-C5.md) · [03 — definições](03-definicoes-das-metricas.md) ·
[05 — política, orçamentos e garantias](05-politica-de-simbolos-e-garantias.md) ·
[06 — erro Latossolo → Argissolo](06-erro-latossolo-argissolo.md) · [07 — errata](07-errata-dos-relatorios-anteriores.md) ·
reconciliação por perfil: `reconciliacao/v2/` e `reconciliacao/v3/` (`perfis.csv`, `sobreposicao.md`,
`contagens.json`), `reconciliacao/v2_x_v3.md`, `reconciliacao/v1_x_v2_emenda6.txt`.

## 1. Localização e isolamento

Cópia confirmada em `<cópia experimental>`;
ambiente `<cópia experimental>/.venv`. Antes de qualquer alteração:
manifesto de `experimento_integracao/` (`manifestos/experimento_integracao-antes-da-auditoria.json`)
e cópia do código da v2 (`codigo_v2/`: `integracao/` e `nucleo/avaliador.py`). A rodada v1
(`resultados/etapa1_integracao/v1_interrompida/`), a v2 (`resultados/etapa1_integracao/`), os
modelos e a configuração anterior não foram tocados (verificação em §9).

## 2. Os números relatados foram conferidos

Recalculados dos registros por perfil da v2 (`reconciliacao/reconcilia.py v2`) e reproduzidos na v3:

| Afirmação anterior | Conferência |
|---|---|
| 3 variantes × 1.084 perfis | ✔ 373 + 483 + 67 + 67 + 94 = 1.084 entradas de conjunto. **Não são 1.084 perfis físicos distintos**: E3, E3b e E4 são os mesmos 94 perfis curados (67 elegíveis em E3/E3b) em versões diferentes |
| observacional preservada em todos | ✔ SHA de classe, conclusão, alcançáveis, pendências e prova idêntico A = B = C em 1.084/1.084 (v2 e v3) |
| nenhuma classe condicional fora do alcançável | ✔ e mais forte do que parecia: **nenhum cenário** saiu do alcançável antes do filtro (0 em v2 e v3); na v1 o filtro removeu 17+ |
| 132 de 371 resolvidos, 84,8% (112), 20 erros | ✔ — mas 371 inclui 14 perfis **sem** classe de referência; os 132 resolvidos têm todos referência; as 112 concordâncias são todas com referência **conclusiva**; das 20 discordâncias, 19 com referência conclusiva e 1 não conclusiva |
| 16,9% e 42,5% na incompletude natural | ✔ 80/473 e 34/80 (referência = ORDEM registrada) |
| +0,008 [−0,035; +0,063] | ✔ +0,0084 — ver §5 |
| 26 e 15 exclusões | ✔ |
| 20 × 12 erros | ✔ |
| Acerto@3 de 1 em 6 | ✔ (rede: horizonte e assinatura; árvores 0/6) |
| tempos 0,20 / 0,49 / 0,77 s | ✔ na v2; na v3, 0,18 / 0,42 / 0,85 s — medidos com 5 processos concorrentes, ruidosos; só a ordem A < rede < árvores é estável |
| "8.972 combinações, todas as formas compatíveis" | ✘ **truncado** (§6) |
| "condicional robusta" 7 e 5 | ✘ afirmada com enumeração incompleta (§7) |

## 3. C4: escopo, pendência e a nova correção C5

Detalhes em [02](02-matriz-C1-C5.md). Em resumo:

* **C4** cobre os predicados derivados em perfis com **B sem sufixo de tipo** (completamentos ∅, t, w,
  i, h; até 3 horizontes). Não cobre identificações com **veto pendente**. Estas são tratadas
  **predicado a predicado**: dos 13 predicados das duas chaves, os 9 que leem identificações
  afirmadas também consultam as pendentes (auditoria estática), e 1.226 preenchimentos compatíveis
  do dado ausente em 294 perfis não acharam violação, com e sem as correções. **Não há defeito
  demonstrado**. A frase do relatório anterior descrevia o mecanismo, não um defeito verificado.
* **C5 (nova, defeito de implementação):** o seletor "B diagnóstico" julgava cada horizonte
  isolado. Caso mínimo: `A / Bwg1 15–40 / Bw2 40–80 / C` → **GLEISSOLO** no núcleo original (5ª e 6ª)
  apesar de 65 cm de B latossólico válido; com C5, **LATOSSOLO**. Corrigido na cópia com teste de
  regressão. Nota normativa preservada: a norma proíbe B diagnóstico *acima* do glei, e a regra
  implementada simplifica para "em todo o perfil" (simplificação declarada na base). A C5 corrige
  a implementação dessa regra, sem resolver a ambiguidade normativa.
* **Efeito da C5 nos conjuntos avaliados:** nenhuma resposta observacional mudou (0 de 1.084 entre
  v2 e v3), e a suíte original `nucleo.testes`, com os números do conjunto curado, continua passando.
  O defeito é real, mas raro nestes acervos.
* **Por que os testes não pegaram:** a ablação produz `B` sem tipo, cujo ramo (pendentes) já usava
  o contexto do perfil; o ramo defeituoso é o das identificações afirmadas, e o efeito exige B
  latossólico subdividido em horizontes de menos de 50 cm com glei em posição diagnóstica. Além
  disso, contenção compara completamentos com o observado: se os dois erram pelo mesmo seletor, a
  contenção não acusa — **contenção não é correção**.

## 4. Reconciliação dos denominadores (E1)

| | rede | árvores |
|---|---:|---:|
| perfis | 373 | 373 |
| com classe de referência | 359 | 359 |
| observacional não conclusiva | 371 (357 com referência) | 371 |
| abstenção em todos os horizontes acionados (sem cenário) | 111 | 134 |
| cenário 1 compatível não conclusivo | 128 | 117 |
| **resolvidos** | **132** | **121** |
| — concordam com a referência | 112 | 109 |
| — discordam | 20 | 12 |
| **referência excluída do cenário 1** | **26** | **15** |
| — porque o cenário 1 conclui outra classe (= as discordâncias) | 20 | 12 |
| — porque o cenário 1, não conclusivo, já não a contém | 6 | 3 |
| referência fora da **união** dos cenários compatíveis (v3) | 1 | 1 |
| robustas (v3, enumeração completa exigida) | 4 | 4 |

371 = 132 + 128 + 111 na rede e 121 + 117 + 134 nas árvores (não conclusivos = resolvidos +
cenário não conclusivo + sem cenário). **Os 20 erros são subconjunto dos 26 casos de exclusão**:
em E1 nenhuma discordância ocorre com a referência já fora do observacional. Os universos coincidem
(perfis com referência no alcançável observacional, 359/359 com C1–C5). As tabelas completas por
conjunto estão em `reconciliacao/v3/sobreposicao.md`, e as linhas por perfil (373 × 3 variantes em
E1, idem nos demais) em `perfis.csv`. Sobreposição entre os modelos: 99 perfis resolvidos pelos
dois, 33 só pela rede, 22 só pelas árvores; exclusão da referência nos dois em 8, só rede 18, só
árvores 7.

## 5. A métrica de +0,008

* **Métrica:** diferença pareada, rede − árvores, na proporção de perfis cuja **melhor resposta
  disponível** (a observacional se conclusiva; senão a classe condicional do cenário 1) é
  **igual à classe de referência** ("certa").
* **Unidade:** fração de perfis; **denominador:** 359 perfis de E1 com classe de referência.
* **Contas:** rede 114 certas, árvores 111 → (114 − 111)/359 = **+0,0084**. Sinal positivo favorece
  a rede.
* **Abstenções e não conclusivos** contam 0 em "certa" (e em "errada"); os erros contam 0 em
  "certa" e 1 em "errada" (rede 20, árvores 12; diferença +0,022, IC [−0,011; +0,046]). A métrica
  "certa" sozinha **recompensa responder mais**: deve ser lida junto com "errada".
* **Intervalo:** reamostragem de **levantamentos** (35 grupos) com reposição, 2.000 vezes, semente
  20261019, média da diferença por perfil em cada reamostra, percentis 2,5% e 97,5% → [−0,035;
  +0,063]. É pareado (mesmos perfis nas duas variantes) e respeita a dependência por levantamento;
  cada perfil tem uma só corrupção. Reproduzido a partir dos registros salvos
  (`reconciliacao/reconcilia.py`, mesma função e semente do experimento).
* **Leitura:** **ausência de superioridade detectável**, não equivalência demonstrada. Nenhuma margem
  de equivalência foi pré-registrada, e o intervalo admite de −3,5 a +6,3 pontos.

## 6. A verificação das 8.972 combinações

O diagnóstico da v2 truncava cada perfil nas **64 primeiras** combinações: 21 perfis afetados,
8.972 de 14.540 combinações, num catálogo de 4 sufixos (t, w, i, h) sem a opção "continua sem tipo".
Refeito sem limite, com o catálogo {∅, t, w, i, h} (s ≡ h no 1º nível; g/f/c/v/m excluídos por
decisão de projeto), nos 373 + 67 perfis de E1 e E3:

| | núcleo original (A0) | corrigido (C1–C5) |
|---|---|---|
| combinações | 31.600 | 31.600 |
| perfis com saída fora do alcançável mascarado | **5** (E1) | **0** |

É **enumeração exaustiva num catálogo finito, nestes perfis**. Não é garantia geral sobre entradas
possíveis. A C2 foi conferida: todo orçamento do núcleo que estoura gera indeterminado com o motivo
no detalhe da derivação. No fluxo, o orçamento de cenários agora aparece em `avaliacao_completa` /
`aviso_orcamento`. Restam sem sinalização explícita só o teto de 30 hipóteses de anotação (registrado
como limitação). Ver [05](05-politica-de-simbolos-e-garantias.md).

## 7. Robustez condicional sob orçamento

Na v2, "condicional robusta" era decidida sobre os cenários avaliados (até 8), mesmo havendo mais
combinações. Na v3 só é afirmada com enumeração completa. Em E1, a enumeração ficou incompleta em
110 perfis (rede) e 87 (árvores), e as robustas caíram de 9 para 4 (rede) e de 6 para 4 (árvores),
contadas sobre todos os perfis. O relatório anterior dava 7 e 5 porque contava só os perfis de
observacional não conclusiva. Nenhuma outra métrica mudou.

## 8. Segurança lógica × correção empírica

| | Afirmação | Verificada em | Resultado |
|---|---|---|---|
| **A. Preservação observacional** | ligar o Inferidor não altera a resposta sobre os dados observados | 1.084 entradas × 3 variantes, v2 e v3; testes de invariância | ✔ 100% |
| **B. Consistência condicional** | cenários de **preenchimento compatível** ficam no alcançável observacional | cenários do experimento (0 fora, antes do filtro); enumeração exaustiva E1+E3 (31.600); veto pendente (1.226); apagamento no curado (168) | ✔ nesses universos e catálogos, com C1–C5; o núcleo original falha em todos |
| **C. Qualidade preditiva** | símbolo e classe condicional correspondem à referência | E1/E3/E3b (referência = núcleo sobre os símbolos originais); E2/E4 (ORDEM registrada) | parcial: 84,8%/90,1% em E1; 42,5%/32,7% contra o rótulo em E2 |

A e B **não garantem** C. As hipóteses de **correção** de anotação (Explicador) substituem informação
observada, alteram a premissa e, corretamente, **não** são submetidas ao teste de contenção: o código
as avalia à parte (`fluxo.hipoteses_de_anotacao`), e os testes não exigem contenção delas.

## 9. Respostas

1. **A integração está funcional no escopo implementado?** Sim. Executa de ponta a ponta nos
   1.084 casos das três variantes, sem falha, com os invariantes A e B verificados. O escopo é o 1º
   nível categórico, a 5ª edição como produção, o recorte de cinco ordens a fundo e oito por triagem,
   e os símbolos ausentes ou sem tipo.
2. **A resposta observacional permanece preservada?** Sim, em 100% dos casos e nas duas rodadas.
   Ela muda em relação ao núcleo original, pelas correções C1–C5, e isso é separado pela variante A0.
3. **A consistência condicional está verificada em quais universos?** Nos cenários do experimento
   (E1–E4), na enumeração exaustiva de E1+E3 (catálogo {∅,t,w,i,h}), nos 294 perfis com veto pendente
   (quatro famílias de preenchimento) e nos 168 apagamentos de símbolo do curado (catálogo de 120
   leituras). Não há garantia geral.
4. **A inferência de símbolos oferece benefício, e a que custo?** Oferece **resolução condicional**:
   em E1, 132 (rede) e 121 (árvores) de 371 perfis não conclusivos, com 112 e 109 concordantes. O
   custo são 20 e 12 classes condicionais discordantes, com a referência excluída do cenário 1 em
   26 e 15 perfis, contra 0 sem inferência. Em incompletude natural (E2) a concordância com o rótulo
   cai para 42,5% e 32,7%. A discordância com o rótulo histórico não é toda erro do modelo, mas a
   fragilidade do rótulo também não autoriza descartá-la. O padrão dominante, Latossolo registrado →
   Argissolo condicional, coincide com um erro de símbolo **confirmado** em E1, onde os símbolos
   originais eram `Bw` ([06](06-erro-latossolo-argissolo.md)).
5. **Há vantagem específica da rede sobre as árvores?** Não detectável onde há referência derivada
   dos símbolos originais (E1: +0,008 [−0,035; +0,063] em acertos, com mais erros da rede). Em E2 a
   rede resolve, acerta **e erra** mais (acertos +0,035 [+0,015; +0,053]; erros +0,023 [+0,011;
   +0,035]) contra um rótulo fraco. Isso é mais resolução, não acurácia superior demonstrada.
6. **Que limitações impedem o uso automático?** Classes condicionais erradas com confiança alta
   (p(t) ≈ 0,75 nos erros Latossolo→Argissolo); θ = 0,5 sem efeito discriminante; escore não
   calibrado; robustez rara (4 perfis de 373 em E1); referência das ablações derivada do próprio
   núcleo; ausência de padrão-ouro na incompletude natural; conflito de anotação com revocação de
   12–28% e falso alerta de 10–14%; dados já examinados (avaliação exploratória); cobertura
   normativa parcial.
7. **O que permanece sem implementação ou avaliação?**
   * níveis 2–4 na integração;
   * edições anteriores à 5ª;
   * calibração conjunta das saídas;
   * regra de abstenção específica para o par t × w (proposta exploratória, não executada);
   * proteção estrutural, e não predicado a predicado, para vetos pendentes;
   * sinalização do teto de hipóteses de anotação;
   * avaliação com dados nunca examinados;
   * amostra de B antigos com tipo confirmado independentemente;
   * busca de melhoria da rede.

## 10. Conclusões, separadas

* **Viabilidade técnica:** demonstrada no escopo, depois de cinco correções do núcleo e uma da
  política. A integração ajudou a achar defeitos de solidez do núcleo.
* **Benefício da inferência de símbolos:** existe como resolução **condicional** em remoção
  artificial do tipo do B, com cerca de 1 erro a cada 6 ou 9 resoluções. Em incompletude natural é
  incerto e desfavorável contra o rótulo.
* **Benefício específico da rede:** não demonstrado.
* **Resolução condicional ≠ conclusão:** nenhuma classe condicional foi contada como resposta
  observacional.
* **Confiabilidade para uso real:** **não estabelecida**. O sistema serve como apoio, com a classe
  condicional marcada e a resposta observacional sempre ao lado, mas não para decisão automática.

A proposta neuro-simbólica não fica confirmada nem refutada por estes resultados.

## 11. Reprodução (a partir de `work/classolosbr-ns/` da cópia)

```bash
PY=../../../../.venv/Scripts/python
AUD=experimento_integracao/auditoria-v3-2026-10-18
$PY -m nucleo.testes
$PY -m integracao.testes
CLASSOLOSBR_SAIDA_EXPERIMENTO=$AUD/resultados $PY -m integracao.experimento rodar E1   # idem E2, E3, E3b, E4
CLASSOLOSBR_SAIDA_EXPERIMENTO=$AUD/resultados $PY -m integracao.experimento agregar
$PY $AUD/reconciliacao/reconcilia.py v2        # e v3
$PY $AUD/reconciliacao/compara_v2_v3.py
$PY $AUD/casos_minimos/contencao_preenchimento_exaustiva.py [--sem-correcoes]
$PY $AUD/casos_minimos/contencao_veto_pendente.py [--sem-correcoes]
$PY $AUD/casos_minimos/auditoria_estatica_predicados.py
$PY $AUD/latossolo/analisa_latossolo_argissolo.py
```

## 12. Arquivos alterados nesta auditoria (só na cópia)

* `nucleo/avaliador.py` — C5 (seletor "B diagnóstico" no contexto do perfil) e comentário do
  interruptor.
* `integracao/fluxo.py` — robustez só com enumeração completa; `avaliacao_completa`,
  `aviso_orcamento`, união dos alcançáveis; versão `integracao-1.1`.
* `integracao/experimento.py` — saída configurável (`CLASSOLOSBR_SAIDA_EXPERIMENTO`); registros com
  todos os cenários e propostas.
* `integracao/testes.py` — `teste_auditoria_v3` (C5, escopo da C4, robustez sob orçamento):
  83 verificações, 0 falhas.
* Novo: todo o diretório `auditoria-v3-2026-10-18/`. O código da v2 está preservado em `codigo_v2/`.

## 13. Verificação final de integridade

* **Originais** (reexame por SHA-256 contra os manifestos de antes da cópia): vault 906/906 e
  diretório LaTeX 71/71 arquivos idênticos — nenhum removido, novo ou alterado.
* **Na cópia:** monografia, avulsos, `main_monografia.tex`, `main_artigo.tex`, PDFs, `ref.bib`,
  figuras, `raw/`, `tools/`, `inferidor/` e resultados históricos idênticos ao original. Diferenças
  só nas declaradas: `nucleo/avaliador.py` alterado; 158 arquivos novos sob `integracao/`,
  `experimento_integracao/` e `nucleo/dados/catalogo_simbolo_ausente.json`.
* **Artefatos experimentais anteriores:** os 96 arquivos de `experimento_integracao/` fora deste
  diretório (v1, v2, modelos, configuração, relatórios, exemplos, diagnósticos) estão idênticos ao
  manifesto tirado no início da auditoria — 0 alterados, 0 removidos, 0 novos.
* ⚠️ `_isolamento/verifica_final.py` regrava, a cada execução, os próprios arquivos de saída
  (`original-*-depois.json`, `copia-*-final.json`, `verificacao-final.json`). Os da sessão anterior
  foram substituídos pelos desta, com o mesmo resultado para os originais; cópia desta verificação
  em `manifestos/verificacao-final-auditoria-v3.json`.
