# O erro "LATOSSOLO de referência → ARGISSOLO condicional"

Fonte: `latossolo/analisa_latossolo_argissolo.py` → `latossolo/casos.json` (por perfil) e
`latossolo/resumo.json`. Universo: perfis da rodada v2 (E1, E2) em que a classe de referência é
LATOSSOLO e o cenário 1 conclui ARGISSOLO na rede **ou** nas árvores. Reexecução com os mesmos
artefatos e o mesmo fluxo; nenhum limiar ajustado; o rótulo não entra como preditor.

| | |
|---|---|
| Perfis | **33** (E1: 7, cuja referência vem dos símbolos originais antes da remoção; E2: 26, referência = ORDEM registrada) |
| Em que modelo | rede e árvores: 22; só rede: 6; só árvores: 5 |
| Símbolos originais antes da remoção (E1) | `Bw1` 6, `Bw2` 6, `Bw3` 4, `Bw4` 1, `Bw` 1 — o modelo errou o símbolo |
| Símbolos anotados (E2) | `B` 21, `B21` 5, `B22` 5, `B1` 4, `B23` 1 (notação antiga, sem tipo) |
| Candidato 1 (média) | rede: κ 0,72, p(t) 0,75, p(w) 0,17; árvores: κ 0,75, p(t) 0,74, p(w) 0,13 |
| `Bw` entre os candidatos | rede em 15 perfis, árvores em 22 — mas só 4 perfis (cada modelo) têm algum cenário avaliado que conclui LATOSSOLO |
| Núcleo com todos os acionados = `Bw` | LATOSSOLO em 15; indeterminado entre NEOSSOLO e LATOSSOLO em 18 |
| Núcleo com todos os acionados = `Bt` | ARGISSOLO em 33 |
| Relação textural (núcleo) | mediana 1,33; ≥ 1,5 em 9 dos 33 |
| Cerosidade nos horizontes acionados | ausente em 48 de 54; grau 2 em 6 |

## Diagnóstico

* **Predição do símbolo** — é a origem. Com confiança alta (p(t) ≈ 0,75), os dois modelos propõem
  `t` em horizontes cuja referência é latossólica. O atributo que mais separa B textural de B
  latossólico no campo, a cerosidade, falta em quase todos esses horizontes, e os modelos recaem na
  frequência de base: `t` é o sufixo mais comum nos B do acervo (já registrado no wiki).
* **Pré-processamento** — não há sinal de defeito: a ausência de cerosidade entra como ausente
  (imputação pela mediana + indicador na rede; ausente nativo nas árvores), como no treino.
  Atributos que distinguiriam melhor (Ki, Kr, ataque sulfúrico, estrutura microgranular detalhada)
  não estão no contrato de entrada.
* **Seleção de candidatos** — `Bw` aparece como alternativa em parte dos casos, mas o escore de
  ordenação o põe abaixo de `Bt`; com o orçamento de 8 cenários e vários horizontes, o cenário com
  `Bw` em todos os horizontes muitas vezes nem é avaliado. Os cenários não avaliados ficam
  declarados na v3 (`avaliacao_completa = false`).
* **Limiar de abstenção** — κ ≈ 0,72 está acima de θ = 0,5. Um θ maior abster-se-ia em parte
  destes casos, mas **não foi ajustado**: escolhê-lo agora, olhando estes perfis, contaminaria a
  avaliação.
* **Cobertura ou formalização do núcleo** — não é a causa: dado o símbolo, o núcleo responde como
  a norma pede (`Bt` → ARGISSOLO, `Bw` → LATOSSOLO ou indeterminado por espessura/Neossolo).
  Os 18 indeterminados com `Bw` mostram que, mesmo com o símbolo certo, parte desses perfis não
  concluiria.

## Melhoria possível (não executada; exploratória)

Escolher θ, ou uma regra de abstenção específica para o par t × w, **na validação** (levantamentos
de treino), usando como critério o erro de assinatura t/w nos B com símbolo, e só então reavaliar
— registrada como etapa exploratória separada, com estes resultados preservados. Não foi feita
nesta auditoria (fora do escopo: sem busca de modelos).
