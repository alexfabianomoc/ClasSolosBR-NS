# Integração completa do ClasSolosBR-NS — relatório técnico comparativo

*Cópia experimental `D:\ClasSolosBR-NS-experimental-2026-10-18\`, 2026-10-18. Nada aqui altera a
monografia, o artigo ou seus resultados; nenhum destes achados foi levado a eles.*

Partes: [01 — isolamento e auditoria](01-isolamento-e-auditoria.md) ·
[02 — correções do núcleo](02-correcoes-do-nucleo.md) · [03 — implementação](03-implementacao.md) ·
[04 — tabelas de resultados](04-resultados-tabelas.md) (geradas de `resultados/etapa1_integracao/resumo.json`).

## Respostas curtas

1. **A integração completa foi executada?** Sim, na cópia: Sentinela → Núcleo (resposta
   observacional) → Camada de Versão → Inferidor (só nos horizontes sem símbolo ou sem tipo) →
   Núcleo (classes condicionais por cenário) → conflitos anotado × proposto → Explicador (hipóteses
   numéricas e de anotação, verificadas por reexecução, com consulta à Versão) → Avaliador Parcial.
   Rodou nos 1.084 perfis de E1–E4 nas três variantes, sem falha de execução, com a resposta
   observacional idêntica com e sem Inferidor em 100% dos perfis e nenhuma classe condicional fora
   do conjunto alcançável observacional — **mas só depois de corrigir quatro defeitos de contenção
   do núcleo (C1–C4) e um da minha própria política** (complementar `B` com `g`/`c`), achados pela
   integração. A rodada v1, antes dessas correções, falhou o critério de contenção e está preservada.
2. **A rede trouxe benefício sobre o sistema sem inferência aprendida?** Sim, **como resolução
   condicional**, não como conclusão: nos perfis com o tipo do B removido artificialmente (E1,
   BDSolos-teste), a rede tornou condicionalmente conclusivos 132 de 371 perfis não conclusivos
   (35,6%), com 112 concordantes e 20 discordantes da classe com os símbolos verdadeiros (84,8%
   [77,8–90,0]). O sistema sem inferência não conclui nenhum. O ganho vem com custo: 20 respostas
   condicionais erradas onde antes havia "não conclusivo" (diferença pareada +0,056 por perfil, IC
   [+0,030; +0,081]). Em incompletude **natural** (E2), a resolução cai para 16,9%, e só 42,5% das
   condicionais concordam com a ordem registrada (referência fraca) — a maior parte dos erros é
   LATOSSOLO registrado → ARGISSOLO condicional (rede propondo `Bt` em B antigos de Latossolos).
3. **Trouxe benefício sobre a alternativa não neural?** **Não demonstrado** no conjunto com
   padrão-ouro: em E1, rede × árvores = +0,008 acerto por perfil, IC [−0,035; +0,063], com mais
   erros da rede (20 × 12). As árvores têm concordância maior (90,1% × 84,8%) e propõem menos. Em
   E2 a rede resolve e acerta mais (acertos +0,035, IC [+0,015; +0,053]) **e também erra mais**
   (+0,023, IC [+0,011; +0,035]), contra referência fraca. Em E3/E3b (curado) os intervalos cruzam
   zero. O ganho comum a B e C — que é a maior parte do efeito — é da **inferência de símbolos**, não
   da rede.
4. **Que erros e custos introduziu?** Classes condicionais discordantes (E1: 20 rede, 12 árvores;
   E2: 46 e 35); exclusão da referência do conjunto do cenário 1 (E1: a classe verdadeira sai do
   alcançável condicional em 26 perfis com a rede e 15 com as árvores, contra 0 na observacional);
   conflitos de anotação com 9,9% (rede) e 14,1% (árvores) de falso alerta e revocação de 28% e 12%
   nas fichas originais; candidatos malformados (2–3%, até 25% com símbolo ausente); tempo mediano
   por perfil de 0,20 s (A) para 0,49 s (rede) e 0,77 s (árvores) em E1, até 8 cenários por perfil.
5. **O que se sustenta e o que fica em aberto:** ver §6.

## 1. Estado de partida e reprodução

Os números da monografia foram reproduzidos exatamente na cópia (`inferidor.selecao`: rede 77,0% /
F1 0,279; árvores 79,7% / F1 0,322). O estimador não neural é o `HistGradientBoostingClassifier`
(um multiclasse + 17 binários, taxa 0,05, `max_iter` 300 com *early stopping* automático ativo,
sem imputação). Não havia modelo salvo: "reutilizar a rede existente" significou retreinar a mesma
configuração, com as mesmas sementes e partição — as métricas de teste do artefato batem com as da
monografia. Detalhes em [01](01-isolamento-e-auditoria.md).

## 2. Correções (separadas da integração)

C1 (símbolo ausente virava falsidade), C2 (truncamento silencioso de leituras), C3 (pendentes
ignorados em agregações por tipo) e C4 (pendentes ignorados em predicados derivados), todas atrás de
uma chave. Efeito isolado pela variante **A0** (núcleo original):

* classe com os símbolos verdadeiros dentro do alcançável observacional: E1 **355/359 (A0) → 359/359
  (A)**; E3b (símbolo apagado) **3/66 → 66/66**; E3 66/66 nas duas;
* contenção sob preenchimento de todo produto `t w i h` dos B mascarados (8.972 completamentos):
  4 perfis violavam em A0, 0 em A;
* respostas observacionais diferentes A0 × A: E1 26, E2 91, E3 1, E3b 67, E4 1 perfis;
* a suíte original `nucleo.testes`, que confere os números do conjunto curado, passa com as correções.

Não se ampliou a cobertura normativa: o `B` sem sufixo continua deixando pendentes só os tipos de B
(decisão de 2026-10-15). Detalhes em [02](02-correcoes-do-nucleo.md).

## 3. Experimento

Pré-registro em `config/experimento.json` (hash antes de qualquer execução: `8a30dc93…`), com seis
emendas datadas e justificadas — cinco antes de executar e **uma depois de ver resultados parciais**
(emenda 6: restrição da complementação e C4, ambas por solidez, não por desempenho). Variantes A0,
A, B, C nos mesmos perfis, mesmo núcleo, mesmo orçamento (3 candidatos/horizonte, 6
horizontes/perfil, 8 cenários/perfil). Partição por levantamento idêntica à de `inferidor.selecao`;
θ e τ escolhidos só na validação. Uma corrupção por perfil; intervalos por reamostragem de
levantamentos (BDSolos) ou perfis (curado).

**Ressalva de independência.** Os perfis de teste nunca foram vistos pelos **modelos**, mas o acervo
inteiro e o conjunto curado foram usados no desenvolvimento das regras. A avaliação é
**exploratória**, com separação rigorosa por grupos — não é teste independente.

| Conjunto | Perfis | Tipo | Referência |
|---|---:|---|---|
| E1 BDSolos-teste, B com tipo → `B` | 373 (35 lev.) | remoção artificial | classe com símbolos verdadeiros |
| E2 BDSolos-teste, incompletude natural | 483 (26 lev.) | natural, sem padrão-ouro | ORDEM registrada (fraca) |
| E3 curado, B com tipo → `B` | 67 | remoção artificial | classe com símbolos verdadeiros |
| E3b curado, 1º B apagado (`''`) | 67 | remoção artificial | idem |
| E4 fichas originais pré-curadoria | 94 | conflitos e Explicador | trocas de símbolo da curadoria |

## 4. Resultados principais

**Resolução condicional e concordância** (entre os perfis cuja resposta observacional não conclui;
a classe condicional nunca é somada à observacional):

| | A | B (rede) | C (árvores) |
|---|---|---|---|
| E1 condicional conclusiva | 0/371 | 132 (35,6%) | 121 (32,6%) |
| E1 concordantes / discordantes | — | 112 / 20 (84,8% [77,8–90,0]) | 109 / 12 (90,1% [83,5–94,2]) |
| E1 condicional robusta (todos os cenários) | 0 | 7 | 5 |
| E3 conclusiva; conc./disc. | 0/67 | 25; 22/3 | 19; 17/2 |
| E3b conclusiva; conc./disc. | 0/67 | 30; 26/4 | 25; 22/3 |
| E2 conclusiva; conc./disc. (fraca) | 0/473 | 80; 34/46 (42,5%) | 52; 17/35 (32,7%) |
| E4 conclusiva | 0/42 | 0 | 0 |

*(Wilson sobre perfis; a dependência por levantamento está nas diferenças pareadas, em [04](04-resultados-tabelas.md).)*

**Propostas e abstenção** (E1, 658 horizontes acionados): rede propõe em 61,9%, árvores em 53,6%;
a abstenção dominante é "o candidato não informa o tipo" (226 / 292). Como κ ≥ 0,5 por construção e
θ = 0,5 saiu da regra pré-registrada, a abstenção por confiança só ocorre quando o modelo dá p > 0,5
a um sufixo que o `B` nega (22 / 13 horizontes). Validade sintática dos candidatos: 98,0% / 97,6%
(E1); 86,1% / 75,1% com símbolo ausente (E3b). Compatibilidade normativa (cenários não vetados): 100%
em E1, 99,7% / 99,9% em E2 (os vetos são `Btw`, B latossólico fino).

**Invariantes** (todos os conjuntos, as três variantes): resposta observacional e Camada de Versão
idênticas A = B = C em 100% dos perfis; 0 violações de contenção; 0 verificações finais violadas;
hipóteses numéricas idênticas entre variantes em 94/94 perfis de E4.

**Explicador e conflitos (E4, fichas originais).** Trocas substantivas de símbolo pela curadoria
nos horizontes não acionados: o conflito sinaliza 14/50 (rede) e 6/50 (árvores); falso alerta
36/362 (9,9%) e 51/362 (14,1%). Divergências (classe registrada fora do alcançável): 8 perfis; 6
deles com troca de símbolo documentada servem de referência para Acerto@k: **rede 0/6 em @1 e 1/6 em
@3** (horizonte e assinatura); árvores 0/6. Hipóteses de anotação verificadas pelo núcleo são raras
(E1: 2 rede, 1 árvores; E2: 1 e 0; E4: 2 e 0). Nos 18 horizontes acionados das fichas originais com
troca documentada, a proposta coincide com a assinatura curada em 3 (rede) e 6 (árvores), com 11 e 7
abstenções.

**Custo.** Tempo por perfil (média / mediana) em E1: A 1,06 / 0,20 s; B 1,54 / 0,49 s; C 1,87 /
0,77 s (as médias são puxadas pelos perfis com vários B sem tipo, em que a C4 avalia até 125
completamentos por predicado derivado; as árvores, com 18 modelos, são mais lentas que a rede). 1.335 (rede) e 1.149 (árvores) cenários em E1, nunca acima de 8 por perfil.
Com símbolo ausente, cada classificação percorre o catálogo de 120 leituras: ~9 s por perfil em
todas as variantes, e a recomendação da próxima determinação ficou inviável nesse caso (emenda 5).

## 5. Erros característicos

* **Latossolo → Argissolo condicional** é o erro dominante: 7 (rede) e 5 (árvores) em E1; 21 e 22
  em E2. Os modelos propõem `Bt` em horizontes B de Latossolos — coerente com o viés já registrado
  no wiki (o sufixo mais frequente nos B do acervo é `t`).
* **Argissolo → Cambissolo** (proposta `Bi`): 6 e 6 em E1.
* Candidatos com dois tipos (`Btw`, `Bit`) aparecem como alternativas; o núcleo veta parte deles.
* Com símbolo ausente, propostas como `Af` são malformadas ou vetadas.

## 6. O que se sustenta e o que fica em aberto

**Sustentado (com as ressalvas da §3):**
* a arquitetura proposta é implementável de ponta a ponta sem que o modelo emita classe, sem
  sobrescrever o símbolo anotado e com a resposta observacional intacta;
* a integração só é sólida depois das correções C1–C4: sem elas, a classe condicional podia sair do
  conjunto alcançável observacional, e apagar um símbolo refutava classes;
* a inferência aprendida de símbolos aumenta a resolução condicional quando o tipo do B é removido
  artificialmente, com concordância entre 85% e 90% contra a classe verdadeira;
* a rede não supera o classificador não neural no conjunto com padrão-ouro; a vantagem comum é da
  inferência, não da rede.

**Em aberto:**
* em incompletude **natural** não há padrão-ouro; a baixa concordância com a ordem registrada (33–43%)
  é preocupante, mas a referência é fraca — falta uma amostra de B antigos com tipo confirmado;
* o valor do conflito anotado × proposto como detector de erro de anotação: revocação de 12–28% e
  Acerto@k em 6 casos não sustentam utilidade;
* a calibração conjunta das saídas (o escore só ordena; κ é heurística);
* a regra de θ (precisão ≥ 0,80 na validação) não discriminou — θ = 0,5 nos dois; outra regra
  (cobertura × precisão) não foi testada;
* defasagem em relação a edições anteriores à 5ª (não implementadas);
* identificações com **veto pendente** em predicados derivados (C4 cobre só o B sem tipo);
* nenhuma busca de melhoria da rede foi feita (opcional no pedido; não executada).

## 7. Arquivos alterados e criados (só na cópia)

* **Alterado:** `work/classolosbr-ns/nucleo/avaliador.py` (C1–C4, atrás de `CORRECOES_INTEGRACAO`).
* **Novos:** `work/classolosbr-ns/integracao/{__init__,modelos,inferidor,fluxo,cli,experimento,testes}.py`;
  `work/classolosbr-ns/nucleo/dados/catalogo_simbolo_ausente.json`;
  `work/classolosbr-ns/experimento_integracao/` (config, modelos, diagnóstico, resultados, exemplos,
  relatório); `_isolamento/` (manifestos e verificação) e `.venv/` na raiz da cópia.
* **Não alterados:** monografia, avulsos, rascunho, `main_monografia.tex`, `main_artigo.tex`, PDFs,
  `ref.bib`, figuras, `inferidor/`, `resultados/` históricos, `raw/`, `tools/` (conferido por hash em
  `_isolamento/verificacao-final.json`).

Reprodução: [`../LEIA-ME.md`](../LEIA-ME.md).

## 8. Verificação final (2026-10-18)

* `nucleo.testes` (suíte original, com C1–C4): tudo passou. `integracao.testes`: 73 verificações,
  0 falhas (`resultados/verificacao_final/`).
* **Original** (`_isolamento/verifica_final.py`, reexame por SHA-256): vault 906/906 e diretório
  LaTeX 71/71 arquivos idênticos aos manifestos de antes da cópia — nenhum removido, novo ou
  alterado.
* **Cópia:** monografia, avulsos, `main_monografia.tex`, `main_artigo.tex`, PDFs, `ref.bib`, figuras,
  `raw/`, `tools/`, `inferidor/` e `resultados/` históricos idênticos ao original. Diferenças só nas
  declaradas: 1 arquivo alterado (`nucleo/avaliador.py`) e 104 novos (`integracao/`,
  `experimento_integracao/`, `nucleo/dados/catalogo_simbolo_ausente.json` — este último cai sob o
  prefixo protegido `nucleo/dados/` por ser arquivo novo, não alteração de dado existente).
