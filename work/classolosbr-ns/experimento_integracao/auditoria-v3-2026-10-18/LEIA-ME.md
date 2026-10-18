# Auditoria v3 da integração (2026-10-18)

Comece por `relatorio/00-relatorio-de-auditoria.md`.

| Pasta | Conteúdo |
|---|---|
| `relatorio/` | 00 auditoria · 02 matriz C1–C5 · 03 definições das métricas · 05 política, orçamentos e garantias · 06 erro Latossolo→Argissolo · 07 errata dos relatórios v2 · **08 encerramento da etapa (formulação final e ressalvas)** |
| `config/` | `rodada-v3.json` (registrada antes da execução) e seu SHA-256 |
| `resultados/` | rodada v3: `E1…E4.jsonl` (por perfil, com todos os cenários), `resumo.json`, logs; `verificacoes/` (suíte original com C1–C5, enumeração exaustiva A0/A1) |
| `reconciliacao/` | `reconcilia.py`; `v2/` e `v3/` (`perfis.csv`, `sobreposicao.md`, `contagens.json`); `v2_x_v3.md/.csv`; `v1_x_v2_emenda6.txt` |
| `casos_minimos/` | contenção sob veto pendente, enumeração exaustiva, auditoria estática dos predicados (scripts e saídas) |
| `latossolo/` | caracterização do erro Latossolo→Argissolo (`casos.json`, `resumo.json`) |
| `codigo_v2/` | cópia do código da integração e de `nucleo/avaliador.py` tal como na rodada v2 |
| `manifestos/` | SHA-256 de `experimento_integracao/` e do código antes da auditoria; verificação final |

Comandos de reprodução: §11 do relatório de auditoria.
