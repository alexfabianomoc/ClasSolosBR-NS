"""Integração de ponta a ponta do ClasSolosBR-NS (cópia experimental, 2026-10-18).

Coordena os seis componentes da arquitetura sem que nenhum deles perca o seu
papel:

    entrada → validação → Sentinela (sinaliza) → Núcleo (resposta observacional)
            → Camada de Versão (cotejo 5ª × 6ª)
            → Inferidor (só nos horizontes sem símbolo ou sem tipo; propõe
              SÍMBOLOS, nunca classe) → Núcleo (classes CONDICIONAIS, por cenário)
            → conflitos anotado × proposto → Explicador (hipóteses numéricas e
              de anotação, separadas, todas verificadas por reexecução)
            → Avaliador Parcial (próxima determinação)

Módulos:
    modelos     — treino e artefato dos dois estimadores (rede e árvores) com a
                  configuração de `inferidor.selecao`, pela mesma interface
    inferidor   — política de candidatos, confiança e abstenção
    fluxo       — `executar(perfil, Configuracao)`: a API interna
    cli         — `python -m integracao.cli ...`
    experimento — variantes A/A0/B/C sobre E1–E4 (pré-registro em
                  `experimento_integracao/config/experimento.json`)
    testes      — `python -m integracao.testes`
"""
