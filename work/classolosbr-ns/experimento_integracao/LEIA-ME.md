# Experimento de integração do Inferidor — cópia experimental

Tudo aqui vive na cópia `D:\ClasSolosBR-NS-experimental-2026-10-18\`, fora da
árvore original. Nada desta pasta foi copiado para o projeto original, para a
monografia ou para o artigo.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `config/experimento.json` | pré-registro (perguntas, variantes, métricas, critérios, partições, sementes, política, orçamento) e emendas, todas anteriores à execução |
| `config/experimento.json.sha256` | hash do pré-registro antes e depois das emendas |
| `config/requirements-venv.txt` | versões do ambiente virtual próprio da cópia (`..\..\..\..\.venv`) |
| `modelos/` | artefatos da rede e das árvores (`*.joblib`), metadados (`*.meta.json`), levantamentos de cada partição |
| `diagnostico/` | scripts que mediram os defeitos antes das correções e geraram o catálogo do símbolo ausente |
| `resultados/etapa0_reproducao/` | reprodução de `inferidor.avaliacao` e `inferidor.selecao` (números históricos) |
| `resultados/correcoes/` | contenção sob apagamento de símbolo, núcleo original (A0) × corrigido (A1); `nucleo.testes` com as correções |
| `resultados/etapa1_integracao/` | `E1…E4.jsonl` (um registro por perfil, quatro variantes), `resumo.json`, logs |
| `exemplos/` | saídas completas com rastreabilidade (`python -m integracao.cli exemplos`) |
| `relatorio/` | relatório técnico comparativo |

## Reprodução (a partir de `work/classolosbr-ns/` da cópia)

```bash
PY=../../../../.venv/Scripts/python          # ambiente da cópia
$PY -m nucleo.testes                         # suíte original, com as correções C1–C3
$PY -m integracao.testes                     # testes da integração
$PY -m inferidor.selecao                     # etapa 0: números da monografia (7 min)
$PY -m integracao.modelos treinar            # artefatos (2,5 min); grava modelos/
$PY -m integracao.experimento rodar E1       # idem E2, E3, E3b, E4
$PY -m integracao.experimento agregar        # resultados/etapa1_integracao/resumo.json
$PY -m integracao.cli executar PERFIL.json --variante B
$PY -m integracao.cli exemplos
$PY experimento_integracao/diagnostico/contencao_simbolo_apagado.py [--sem-correcoes]
```

O núcleo original (sem C1–C3) é reproduzido com `nucleo.avaliador.CORRECOES_INTEGRACAO = False`.
