# Encerramento da etapa experimental (2026-10-18)

Este arquivo fecha a etapa sem alterar os relatórios anteriores e prevalece sobre eles onde
houver diferença de formulação.

## Formulação de encerramento

> A integração executada preservou a resposta observacional e apresentou consistência nos cenários
> examinados. A inferência de símbolos ampliou a resolução condicional, com erros adicionais. Não
> foi demonstrada vantagem específica da rede neural sobre as árvores de gradiente. A avaliação é
> exploratória e parcialmente baseada em referências produzidas pelo próprio núcleo, exigindo
> calibração e validação independente antes de uso automático.

## Ressalvas que acompanham a formulação

1. **Referência produzida pelo próprio núcleo.** Em E1, E3 e E3b, a classe de referência é a que o
   núcleo deriva dos símbolos originais antes da remoção. A concordância (84,8% na rede, 90,1% nas
   árvores, em E1) mede sobretudo a **recuperação da classificação anterior à remoção**; não
   demonstra, isoladamente, correção pedológica independente.
2. **Confiança não é critério de aceitação.** Nos erros Latossolo → Argissolo, o candidato errado
   teve p(t) ≈ 0,75 e κ ≈ 0,72. O escore não deve orientar aceitação automática. A consistência
   lógica de um cenário (ficar no conjunto alcançável) não garante que a premissa inferida — o
   símbolo — corresponda ao solo.
3. **Escopo entregue.** A integração foi concluída para o **primeiro nível categórico sob a 5ª
   edição** (com a 6ª como contraprova na Camada de Versão). Onde os relatórios anteriores falam em
   "proposta completa" ou "integração completa", leia-se: **o fluxo dos seis componentes executado de
   ponta a ponta nesse escopo**. Continuam pendentes, entre outros: níveis 2–4 na integração,
   edições anteriores à 5ª, calibração conjunta das saídas do Inferidor, avaliação com dados nunca
   examinados e proteção estrutural (não predicado a predicado) para vetos pendentes.
4. **Sobre a C5.** A correção é relevante mesmo sem ter alterado nenhum resultado nos 1.084 casos:
   mostra que a suíte anterior e os conjuntos avaliados não cobriam aquele comportamento. Ela melhora
   a implementação do núcleo, mas **não acrescenta evidência de desempenho da rede**.
