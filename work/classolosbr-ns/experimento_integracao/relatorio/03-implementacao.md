# 3. Implementação do fluxo integrado

## 3.1 Interface

* **API interna:** `integracao.fluxo.executar(perfil_bruto, Configuracao(...)) → dict`
  (JSON serializável). `Configuracao(inferidor=None | Inferidor(Estimador), detector=…,
  classe_registrada=…, recomendar=…, explicador_numerico=…, max_cenarios=8,
  max_horizontes_inferidos=6, edicao="5")`.
* **Comando:** `python -m integracao.cli executar PERFIL.json --variante A|B|C [--json SAIDA]`
  e `python -m integracao.cli exemplos`.
* **Modelos:** `python -m integracao.modelos treinar|conferir`; `integracao.modelos.Estimador`
  é a interface comum (rede e árvores), com `proba(linhas_de_atributos)`.

## 3.2 Ordem das operações (e por que nessa ordem)

1. **Validação** e cópia profunda da entrada; SHA-256 da entrada antes e depois.
2. **Sentinela** — gramática do símbolo e escore de anomalia (detector ajustado nos 94 curados,
   sem o próprio perfil). Só sinaliza.
3. **Núcleo, resposta observacional** — antes de qualquer inferência, para que nada do que vem
   depois possa alterá-la.
4. **Camada de Versão** — `cotejar` na 5ª e na 6ª, causas da não conclusão, categorias.
5. **Gatilhos** — horizonte com símbolo ausente, B sem sufixo de tipo ou leituras discordantes.
6. **Inferidor** — propostas (até 3 candidatos por horizonte) ou abstenção, com motivo.
7. **Núcleo, cenários** — produto limitado dos candidatos (até 6 horizontes, 8 cenários, em
   ordem do escore de ordenação), cada um reexecutado numa cópia; veto do dado ou saída fora do
   alcançável observacional ⇒ cenário **incompatível**, excluído da classe condicional.
8. **Conflitos anotado × proposto** — nos horizontes de símbolo informativo (sinal
   1 − escore(anotado) ≥ τ e assinatura diferente). Hipóteses; nada é alterado.
9. **Explicador** — só se a classe registrada sai do alcançável observacional: hipóteses
   numéricas (`nucleo.explicador.explicar`, ordenadas com o Sentinela) e de anotação
   (substituição/complementação do símbolo em cópias do perfil), em listas separadas, todas
   reexecutadas; "verificada" só quando o núcleo deriva a classe registrada.
10. **Avaliador Parcial** — `nucleo.medicao.recomendar` sobre a resposta observacional.
11. **Verificações** — entrada preservada, símbolos anotados intactos, condicionais contidas no
    observacional, Inferidor sem classe.

## 3.3 Invariantes: onde são garantidos e onde são testados

| Invariante | Mecanismo | Teste (`integracao.testes`) / medida |
|---|---|---|
| Modelo não emite classe | `Inferidor` devolve `Proposta`/`Candidato` (símbolos); a classe só sai de `classificar` | `inferidor_nao_emite_classe` em toda saída |
| Símbolo proposto não sobrescreve o anotado | cenários e hipóteses usam `copy.deepcopy`; símbolo anotado conferido no fim | `teste_preservacao_e_invariancia`, `teste_conflito_e_explicador` |
| Resposta observacional sempre disponível | calculada antes do Inferidor; modelo indisponível ou com exceção ⇒ abstenção | `teste_indisponibilidade`; M8 no experimento |
| Classe com símbolo inferido é condicional | só existe em `condicional.cenarios[*]`, com `condicional: true` e aviso | `teste_rastreabilidade` |
| Prova identifica símbolo, modelo, confiança, cenário | `_anotador`: nós da prova que citam o horizonte substituído recebem `simbolos_inferidos` | `teste_rastreabilidade` |
| Confiança ≠ prova | escore declarado "de ordenação, não calibrado"; κ decide abstenção; aviso no cenário | idem |
| Abstenção possível | κ < θ, candidato sem tipo, principal "outro", candidato malformado, modelo indisponível | `teste_acionamento_e_abstencao` |
| Ausência não vira falsidade | correções C1–C4 no núcleo | `teste_correcoes`, `teste_contencao_preenchimento`, diagnósticos de contenção |
| Hipótese só "restabelece" após reexecução | `verificada = classificar(cópia).classe == registrada` | `teste_conflito_e_explicador` (com reexecução independente) |
| Contrafactual ≠ causa | campo `natureza` de toda hipótese | idem |
| Sentinela não altera a decisão | o escore só entra em `explicar(sentinela=…)` (ordem) | `teste_preservacao_e_invariancia` |
| Recorte normativo respeitado | nenhuma regra nova; `B` sem tipo só completa tipos de B | emenda 6; `teste_acionamento_e_abstencao` |

## 3.4 Política do Inferidor (resumo)

* **Complementação** do `B` sem tipo: prefixo e principal anotados + sufixos de **tipo de B**
  decididos pelo limiar de cada sufixo (`t w i h s`); alternativas invertendo os sufixos de tipo
  de B mais próximos do limiar. **Proposta completa** só quando o símbolo está ausente.
  **Seleção entre leituras** da norma quando o símbolo antigo tem leituras discordantes.
* **Escore de ordenação** P(principal) × Π[p_s ou 1 − p_s]: só ordena; não é probabilidade
  conjunta calibrada (as saídas são marginais, e os sufixos não são independentes).
* **κ** = menor confiança entre as decisões sobre os 9 sufixos de tipo; abstenção se κ < θ.
  θ pela regra pré-registrada na validação: 0,50 nos dois modelos (precisão seletiva já ≥ 0,80
  no menor θ). Na prática, a abstenção vem de "candidato não informa o tipo" e, depois da
  emenda 6, de κ < 0,5 quando o modelo dá p > 0,5 a g/f/c/v num `B` sem tipo.
* **τ** do conflito: 0,9944 (rede) e 0,9826 (árvores), fixados para sinalizar 10% da validação.
* **Orçamento:** 3 candidatos/horizonte, 6 horizontes inferidos/perfil, 8 cenários/perfil, 30
  hipóteses de anotação/perfil.
