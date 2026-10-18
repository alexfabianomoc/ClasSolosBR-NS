# Rodada v1 — interrompida em 2026-10-18 (preservada)

Interrompida pelo agente depois de uma agregação parcial (E1 152, E2 67, E3 37, E3b 1, E4 47 perfis; até a
interrupção efetiva, os arquivos chegaram a E1 251, E2 87, E3 54, E3b 3, E4 61 registros),
porque 17 cenários condicionais saíram do conjunto alcançável observacional (critério de falha do
pré-registro, M5). O fluxo já os marcava como incompatíveis e não os usava como classe condicional,
mas a ocorrência revelou dois defeitos:

1. **Política do Inferidor (integração):** na complementação de um `B` sem sufixo de tipo, o
   candidato podia acrescentar `g`, `c`, `f` ou `v`. Pela decisão de 2026-10-15, o `B` sem sufixo só
   deixa pendentes os tipos de B; acrescentar glei/concrecionário contradiz a anotação e é hipótese de
   anotação, não complemento. 15 dos 17 cenários (Plintossolo/Gleissolo fora do alcançável).
2. **Núcleo (C4):** predicados derivados (ex.: `requisitos_argissolos_5ed`) só enxergam os B textural
   afirmados; com os B pendentes, o topo do B textural passava a ser o `Btf` a 130 cm e o Argissolo era
   refutado (`BDSolos|598|5818|Perfil no 11`, 2 cenários).

Os registros parciais ficam aqui como estavam. Os resultados válidos são os da rodada v2, na pasta-mãe.
