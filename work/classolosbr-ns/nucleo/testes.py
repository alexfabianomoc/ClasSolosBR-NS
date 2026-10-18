"""Testes do núcleo simbólico. Sem dependências: `python -m nucleo.testes`.

Cobrem três coisas, nesta ordem de importância:

1. as **tabelas de verdade** de três valores, das quais depende a propriedade
   de corretude do Avaliador Parcial;
2. os **casos reais** do conjunto curado que motivaram cada correção — cada
   teste nomeia o perfil e o defeito que ele pegou;
3. a **regressão do caso-testemunha**, `GeoTab_RN_007_Acu`, cujo empate de
   50/50 na atividade da argila é a lacuna da norma que o SmartSolos
   identificou e a 6ª edição creditou.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .avaliador import avaliar, classificar
from .chave5 import CHAVE_5ED
from .chave6 import CHAVE_6ED
from .edicoes import assimetrias, cotejar, diferencas_nao_documentadas
from .horizontes import (PREDICADOS, PROFUNDIDADE_EXCLUSAO_ARENOSA,
                         _cor_palida_precedente, identificar,
                         relacao_textural, tipos_de)
from .horizontes import gs  # gramática de sufixos do sentinela
from .logica import F, I, V, e3, nao3, ou3
from .perfil import Horizonte, Perfil, carregar_json

PYKKA7 = Path(__file__).resolve().parents[3] / "raw" / "pykka7-smartsolos-dataset"
ORIGINAIS = Path(__file__).resolve().parents[1] / "transcricao" / "originais"

_falhas: list[str] = []


def confere(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


def perfil(caminho: str) -> Perfil:
    return carregar_json(PYKKA7 / caminho)[0]


def regra(classe: str):
    return next(r for r in CHAVE_6ED if r.classe == classe)


# ------------------------------------------------------- lógica de 3 valores -

def teste_logica() -> None:
    print("\nlógica de três valores (Kleene forte)")
    confere(e3([V, F, I]) is F, "um falso refuta a conjunção, mesmo com indeterminado")
    confere(e3([V, I]) is I, "verdadeiro com indeterminado é indeterminado")
    confere(e3([V, V]) is V, "só verdadeiros satisfazem")
    confere(ou3([F, I, V]) is V, "um verdadeiro satisfaz a disjunção")
    confere(ou3([F, I]) is I, "falso com indeterminado é indeterminado")
    confere(ou3([F, F]) is F, "só falsos refutam a disjunção")
    confere(nao3(I) is I, "o indeterminado é seu próprio complemento")


# ------------------------------------------------- atributos derivados -------

def teste_derivados() -> None:
    print("\natributos derivados do complexo sortivo")
    h = Horizonte("Bt1", 20, 60, {
        "CA_TROC": 4.0, "MG_TROC": 2.0, "K_TROC": 0.2, "NA_TROC": 0.3,
        "H_TROC": 2.5, "AL_TROC": 1.0, "ARGILA": 250.0,
    })
    p = Perfil("teste", [h])
    from .perfil import _derivados
    d = _derivados(h)
    confere(abs(d["SOMA_BASES"] - 6.5) < 1e-9, "S = Ca + Mg + K + Na")
    confere(abs(d["CTC"] - 10.0) < 1e-9, "T = S + H + Al")
    confere(abs(d["V_PERCENT"] - 65.0) < 1e-9, "V% = 100·S/T")
    confere(abs(d["ATIVIDADE_ARGILA"] - 40.0) < 1e-9, "Ta = 1000·T/argila")

    sem_al = Horizonte("Bt2", 60, 90, {"CA_TROC": 1.0, "MG_TROC": 1.0,
                                       "K_TROC": 0.1, "NA_TROC": 0.1})
    confere(_derivados(sem_al).get("V_PERCENT") is None,
            "parcela ausente propaga None, e não zero")


# --------------------------------------------------- casos reais corrigidos --

def teste_relacao_textural() -> None:
    """Os três exemplos da Tabela 1.1 do SiBCS 6ª ed., Cap. 1.

    A norma publica os cálculos com o resultado; usá-los como caso de teste é
    a única forma de saber que a implementação lê a fórmula, e não uma
    lembrança dela.
    """
    print("\nrelação textural B/A — exemplos da Tabela 1.1 da norma")

    def monta(linhas):
        return Perfil("tabela-1.1", [
            Horizonte(s, sup, inf, {"ARGILA": float(arg)})
            for s, sup, inf, arg in linhas
        ])

    ex1 = monta([("A", 0, 10, 120), ("BA", 10, 20, 180),
                 ("Bt1", 20, 45, 280), ("Bt2", 45, 90, 340)])
    confere(abs(relacao_textural(ex1) - 1.92) < 0.005,
            f"exemplo 1: A < 15 cm → seção de 30 cm, exclui Bt2 → 1,92 "
            f"(obtido {relacao_textural(ex1):.2f})")

    ex2 = monta([("Ap", 0, 10, 230), ("AB", 10, 30, 270), ("BA", 30, 50, 370),
                 ("Bt1", 50, 89, 440), ("Bt2", 89, 150, 540)])
    confere(abs(relacao_textural(ex2) - 1.80) < 0.005,
            f"exemplo 2: A inclui AB; Bt2 começa dentro da seção e entra "
            f"inteiro → 1,80 (obtido {relacao_textural(ex2):.2f})")

    ex3 = monta([("A1", 0, 12, 120), ("A2", 12, 35, 180), ("Bt1", 35, 55, 320),
                 ("Bt2", 55, 80, 380), ("BC", 80, 120, 300)])
    confere(abs(relacao_textural(ex3) - 2.33) < 0.005,
            f"exemplo 3: BC fica de fora mesmo dentro da seção → 2,33 "
            f"(obtido {relacao_textural(ex3):.2f})")

    p = perfil("PE/json/GeoTab_PE_032_Paudalho.json")
    confere(abs(relacao_textural(p) - 1.40) < 0.005,
            "PE_032: 1,40 pela fórmula da norma — a aproximação anterior dava "
            "1,53 e vetava um B latossólico legítimo")


def teste_adjacencia_transicional() -> None:
    print("\nadjacência tolera horizontes transicionais")
    p = perfil("PE/json/GeoTab_PE_031_Itambe.json")
    r = classificar(p, CHAVE_6ED)
    confere(r.classe == "LATOSSOLO",
            "PE_031 (A1..A4 A/B B/A Bw): o Bw continua 'imediatamente abaixo "
            "do A' com transicionais interpostos")


def teste_lacuna_de_descricao() -> None:
    print("\nlacuna na descrição não refuta")
    p = perfil("PE/json/GeoTab_PE_025_Barreiros.json")
    r = classificar(p, CHAVE_6ED)
    confere("GLEISSOLO" in (r.alcancaveis + [r.classe or ""]),
            "PE_025 (Ap 0-15, Cg1 30-50): os 15 cm não descritos deixam o "
            "Gleissolo alcançável, em vez de refutado")


def teste_a_chernozemico_estrito() -> None:
    print("\nA chernozêmico exige evidência conjugada")
    for caminho, nome in [("PE/json/GeoTab_PE_039_Passira.json", "PE_039"),
                          ("PE/json/GeoTab_PE_040_Timbauba.json", "PE_040")]:
        p = perfil(caminho)
        r = classificar(p, CHAVE_6ED)
        confere(r.classe != "CHERNOSSOLO",
                f"{nome} (Luvissolo real) não é afirmado Chernossolo — "
                "critério frouxo produzia falso positivo")


def teste_plintico_nao_vem_do_sufixo() -> None:
    """O sufixo `f` é plintita (material); plíntico é horizonte diagnóstico.

    🚨 Regressão de `GeoTab_RN_043_Pedro_Avelino` (2026-09-17). Ler o `f` como
    horizonte plíntico fazia o núcleo afirmar PLINTOSSOLO num perfil que os
    curadores reclassificaram **de** Plintossolo **para** Luvissolo, mantendo o
    `f` — plintita existe, horizonte plíntico não. Os seis perfis do acervo com
    sufixo `f` cobrem as quatro situações de registro de cor, e são a única
    defesa contra a volta do atalho.
    """
    print("\nplíntico não se afirma pelo sufixo f")
    casos = [
        # (arquivo, horizonte, plíntico válido?, por quê)
        ("RN/json/GeoTab_RN_043_Pedro_Avelino.json", "Btfn1", False,
         "matriz 2.5YR 4/8 sem mosqueado claro — sem o arranjo de cores"),
        ("RN/json/GeoTab_RN_003_Pedra_Grande.json", "Btf", False,
         "10 cm de espessura, abaixo dos 15 cm mínimos"),
        ("RN/json/GeoTab_RN_005_Macau.json", "Btf", False,
         "matriz 7.5YR 6/6 — croma acima do admitido para cor clara"),
        ("PE/json/GeoTab_PE_048_Goiana.json", "2Btf", True,
         "mosqueados 10YR 6/3 e 2.5YR 3/6 — o arranjo da norma, sem matriz"),
        ("RN/json/GeoTab_RN_044_Mossoro.json", "Btf", True,
         "mosqueados 2.5YR 5/8 e 10YR 6/3 — o arranjo da norma, sem matriz"),
        ("RN/json/GeoTab_RN_042_Santo_Antonio.json", "Btf", True,
         "matriz 10YR 6/3 é cor clara — falta o registro do mosqueado, "
         "e falta de registro não refuta"),
    ]
    for caminho, simbolo, esperado, motivo in casos:
        p = perfil(caminho)
        h = next(h for h in p.horizontes if h.simbolo == simbolo)
        tem = "plíntico" in tipos_de(p, h)
        confere(tem is esperado,
                f"{p.id_ponto.split('_', 1)[1]} {simbolo}: plíntico "
                f"{'afirmado' if esperado else 'vetado'} — {motivo}")

    # O desfecho que importa: a classe registrada volta a ser alcançável.
    p = perfil("RN/json/GeoTab_RN_043_Pedro_Avelino.json")
    r = classificar(p, CHAVE_5ED)
    confere("LUVISSOLO" in (r.alcancaveis + [r.classe or ""]),
            "RN_043: o Luvissolo registrado volta ao conjunto alcançável")
    confere(r.classe != "PLINTOSSOLO",
            "RN_043: o núcleo não afirma mais o Plintossolo que a curadoria "
            "havia retirado")


# ------------------------------------------------------- caso-testemunha ----

def teste_empate_da_atividade_da_argila() -> None:
    print("\ncaso-testemunha: a lacuna da norma reproduzida como indeterminação")
    p = perfil("RN/json/GeoTab_RN_007_Acu.json")
    derivacao = avaliar(regra("LUVISSOLO").condicao, p)
    confere(derivacao.valor is I,
            "RN_007_Acu: a regra do Luvissolo é indeterminada, não falsa")

    no = next(n for n in derivacao.filhos if "ATIVIDADE_ARGILA" in n.rotulo)
    confere(no.valor is I and "50%" in no.detalhe,
            "o empate de 50/50 na seção de controle de 100 cm é detectado")
    confere("não prevê desempate" in no.detalhe,
            "e a saída diz que a norma não decide — não é um 'unknown' mudo")

    r = classificar(p, CHAVE_6ED)
    confere("LUVISSOLO" in r.alcancaveis,
            "o Luvissolo permanece alcançável, preservando a contenção")


def teste_condicao_b_dos_plintossolos() -> None:
    """A condição (b): plíntico até 200 cm em posição diagnóstica.

    🚨 Regressão de `GeoTab_RN_042_Santo_Antonio` (2026-09-17). A versão
    anterior da condição resolvia glei, A e E e improvisava o resto: qualquer
    mosqueado registrado servia, e "cor pálida" era croma ≤ 2 com valor ≥ 5,
    números que não estão na norma. O critério inventado refutava um
    Plintossolo real cujo `Btf` inicia a 110 cm sob um `Bt` 10YR 6/3.

    ⚠️ Cobre também a **diferença entre as edições**, que é real: a 6ª exige
    valor ≥ 5 no item (b) e estende o item (a) aos matizes mais acinzentados.
    """
    print("\ncondição (b) dos Plintossolos, pela norma de cada edição")
    b5 = PREDICADOS["plíntico até 200 cm em posição diagnóstica (5ª ed.)"]
    b6 = PREDICADOS["plíntico até 200 cm em posição diagnóstica (6ª ed.)"]

    p = perfil("RN/json/GeoTab_RN_042_Santo_Antonio.json")
    valor, detalhe = b5(p)
    confere(valor is V and "10YR 6/3" in detalhe,
            "RN_042: Btf a 110 cm sob Bt 10YR 6/3 satisfaz a condição (b) — "
            "pálido pelo item (b) da norma, não por croma inventado")
    confere(b6(p)[0] is V,
            "RN_042: satisfaz também pela 6ª edição, cujo item (b) exige "
            "valor >= 5 (o Bt tem valor 6)")
    r = classificar(p, CHAVE_5ED)
    confere("PLINTOSSOLO" in ([r.classe or ""] + r.alcancaveis),
            "RN_042: o Plintossolo registrado volta ao conjunto alcançável")

    p = perfil("PE/json/GeoTab_PE_048_Goiana.json")
    valor, detalhe = b5(p)
    confere(valor is V and "variegada" in detalhe,
            "PE_048: 2Btf a 93 cm sob 2Bt sem matriz e com duas cores, uma "
            "pálida — é coloração variegada, não o caso do mosqueado abundante")

    # ---- a especificação de cor, por edição ----
    confere(_cor_palida_precedente("10YR", 6, 3, "5") is True
            and _cor_palida_precedente("10YR", 6, 3, "6") is True,
            "10YR 6/3 é pálido nas duas edições")
    confere(_cor_palida_precedente("10YR", 4, 3, "5") is True
            and _cor_palida_precedente("10YR", 4, 3, "6") is False,
            "10YR 4/3 é pálido só na 5ª — a 6ª exige valor >= 5")
    confere(_cor_palida_precedente("5Y", 4, 2, "5") is True,
            "matiz 5Y é pálido por si, sem restrição de croma (item a)")
    confere(_cor_palida_precedente("5GY", 5, 2, "5") is False
            and _cor_palida_precedente("5GY", 5, 2, "6") is True,
            "matiz esverdeado é pálido só na 6ª, que estendeu o item (a)")
    confere(_cor_palida_precedente("2.5YR", 4, 8, "5") is False,
            "2.5YR 4/8 não é pálido — matiz avermelhado")
    confere(_cor_palida_precedente("10 YR", 6, 3, "5") is True,
            "'10 YR' com espaço interno é reconhecido — o acervo registra "
            "assim em doze horizontes")
    confere(_cor_palida_precedente("19YR", 6, 3, "5") is None,
            "matiz com erro de digitação é indeterminado, nunca refutação")


def teste_rn021_notacao_e_exclusao_textural() -> None:
    """O Gleissolo que dependia de duas correções independentes.

    🚨 `GeoTab_RN_021_Ceara_Mirim` foi a **última violação de contenção** do
    conjunto curado, e precisou de dois consertos que nada têm entre si:

    1. os símbolos `11C1g` e `111C2` são `IIC1g` e `IIIC2` com o numeral
       romano transcrito como dígito — sem reconhecê-los, o horizonte glei não
       era identificado e a classe caía no resíduo;
    2. a exclusão textural dos Gleissolos estava com o **quantificador
       invertido**: refutava no primeiro horizonte arenoso, quando a norma só
       exclui o perfil cuja textura é areia ou areia franca em **todos** os
       horizontes da seção. O perfil tem 330 e 360 g/kg de argila nos dois
       primeiros horizontes e 80 no terceiro.
    """
    print("\nRN_021: notação romana transcrita e exclusão textural")
    p = perfil("RN/json/GeoTab_RN_021_Ceara_Mirim.json")

    confere(gs.moderniza("11C1g") == "2CBg",
            "'11C1g' é lido como 'IIC1g' e modernizado para '2CBg'")
    confere(gs.moderniza("111C2") == "3C2",
            "'111C2' é lido como 'IIIC2' e modernizado para '3C2'")
    confere(gs.moderniza("1C") is None,
            "um '1' isolado não é modernizado — seria adivinhação")
    codigos = {a.codigo for a in gs.valida("11C1g")}
    confere("ROMANO_TRANSCRITO" in codigos,
            "o sentinela sinaliza a corrupção do numeral na transcrição")

    glei = [h for h in p.horizontes if "glei" in tipos_de(p, h)]
    confere([h.simbolo for h in glei] == ["11C1g"],
            "o horizonte glei é identificado pelo símbolo modernizado")

    excl5 = PREDICADOS["sem textura areia exclusiva até 150 cm (5ª ed.)"]
    valor, detalhe = excl5(p)
    confere(valor is V and "AP" in detalhe,
            "a exclusão textural não se aplica: o AP não é arenoso, logo a "
            "textura não é exclusivamente areia")

    r = classificar(p, CHAVE_5ED)
    confere(r.classe == "GLEISSOLO",
            "RN_021 é classificado GLEISSOLO, como a ficha registra")

    # A seção da exclusão difere entre as edições: 150 cm na 5ª, 200 na 6ª.
    confere(PROFUNDIDADE_EXCLUSAO_ARENOSA["5"] == 150
            and PROFUNDIDADE_EXCLUSAO_ARENOSA["6"] == 200,
            "a seção da exclusão textural é 150 cm na 5ª edição e 200 cm na 6ª")


def teste_glei_30cm_so_na_6ed() -> None:
    """A exigência dos 30 cm do glei não pode vazar para a base da 5ª.

    🚨 Regressão de 2026-09-18. O predicado `glei em posição diagnóstica` era
    um só, documentava a 6ª edição e era usado também pela base da 5ª. Com isso,
    a base de produção exigia que o glei dos primeiros 50 cm ocupasse a maior
    parte dos 30 cm abaixo do A — exigência que a 5ª edição não faz, na chave
    (Cap. 4) nem no capítulo (Cap. 9). Dois Gleissolos registrados ficavam
    indeterminados por causa de 15 cm não descritos.

    ⚠️ O defeito era **invisível** a `teste_comparabilidade_das_bases`: com o
    mesmo nome nas duas bases, o predicado tinha a mesma estrutura. Este teste
    fixa o comportamento **por edição**, que é o que a auditoria não vê.
    """
    print("\nexigência dos 30 cm do glei: só na 6ª edição")
    g5 = PREDICADOS["glei em posição diagnóstica (5ª ed.)"]
    g6 = PREDICADOS["glei em posição diagnóstica (6ª ed.)"]

    for caminho, nome in [("PE/json/GeoTab_PE_025_Barreiros.json", "PE_025"),
                          ("PE/json/GeoTab_PE_026_Agua_Preta.json", "PE_026")]:
        p = perfil(caminho)
        v5, d5 = g5(p)
        confere(v5 is V and "ocupa" not in d5,
                f"{nome}: pela 5ª, glei iniciando nos primeiros 50 cm basta — "
                "sem medir ocupação")
        confere(g6(p)[0] is I,
                f"{nome}: pela 6ª, a ocupação dos 30 cm não é mensurável (15 cm "
                "não descritos) — indeterminado, não falso")
        r = classificar(p, CHAVE_5ED)
        confere(r.classe == "GLEISSOLO" and not r.alcancaveis,
                f"{nome}: a base de produção conclui GLEISSOLO, como a ficha")

    usos5 = [r_.classe for r_ in CHAVE_5ED
             if "(6ª ed.)" in str(r_.condicao)]
    confere(not usos5,
            "nenhuma regra da base da 5ª usa predicado marcado como da 6ª")


def teste_contencao() -> None:
    print("\npropriedade de contenção sobre o conjunto curado")
    import unicodedata

    def limpo(t):
        return "".join(c for c in unicodedata.normalize("NFD", (t or "").upper())
                       if unicodedata.category(c) != "Mn")

    arquivos = [a for a in sorted(PYKKA7.rglob("*.json"))
                if not a.name.endswith("_all.json")]
    violacoes = []
    for arquivo in arquivos:
        for p in carregar_json(arquivo):
            registrado = limpo(p.classe_registrada[0])
            if not registrado or registrado == "UNKNOWN":
                continue
            r = classificar(p, CHAVE_6ED)
            possiveis = {limpo(c) for c in r.alcancaveis + [r.classe or ""]}
            # ⚠️ Espodossolos não entram: a 6ª edição extinguiu as subordens
            # da 5ª, e o rótulo do conjunto é 5ª edição.
            if registrado not in possiveis and registrado != "ESPODOSSOLO":
                violacoes.append((p.id_ponto, registrado, r.resumo()))
    confere(True, f"{len(arquivos)} perfis avaliados; "
                  f"{len(violacoes)} classes registradas fora do conjunto alcançável")
    for v in violacoes:
        print(f"       ⚠️ {v[0]}: registrado {v[1]}, derivado {v[2]}")
def teste_comparabilidade_das_bases() -> None:
    """A base da 5ª edição só pode diferir da 6ª onde as edições diferem.

    Sem esta salvaguarda o módulo versão-consciente vira gerador de falsos
    positivos: qualquer descuido de modelagem numa das bases apareceria na
    saída como se fosse diferença de norma.
    """
    print("\ncomparabilidade entre as bases das duas edições")
    confere(len(CHAVE_5ED) == 13, "a chave da 5ª edição tem as treze ordens")

    sequencia = [r.classe for r in CHAVE_5ED]
    esperada = ["ORGANOSSOLO", "NEOSSOLO", "VERTISSOLO", "ESPODOSSOLO",
                "PLANOSSOLO", "GLEISSOLO", "LATOSSOLO", "CHERNOSSOLO",
                "CAMBISSOLO", "PLINTOSSOLO", "LUVISSOLO", "NITOSSOLO",
                "ARGISSOLO"]
    confere(sequencia == esperada,
            "a sequência de precedência é a publicada na 5ª edição (Cap. 4)")

    recorte5 = {r.classe for r in CHAVE_5ED if r.no_recorte}
    recorte6 = {r.classe for r in CHAVE_6ED if r.no_recorte}
    confere(recorte5 == recorte6,
            "o recorte implementado a fundo é o mesmo nas duas bases")

    suspeitas = [a for a in assimetrias() if a.startswith("⚠️")]
    confere(not suspeitas,
            "nenhuma assimetria de modelagem não intencional entre as bases")
    for a in suspeitas:
        print(f"       {a}")

    # Monografia, seção 4.2.1: "um teste falha quando surge alguma [diferença]
    # que não esteja documentada". Até 2026-10-14 o texto prometia e o teste
    # não fazia — só a diferença de recorte reprovava.
    pendentes = diferencas_nao_documentadas()
    confere(not pendentes,
            "toda diferença entre as bases está documentada, com a passagem "
            "da norma, e todo registro corresponde a uma diferença real")
    for a in pendentes:
        print(f"       {a}")


def teste_divergencia_cambissolo_argissolo() -> None:
    """O caso Cambissolo × Argissolo: decidido na 5ª, ambíguo na 6ª.

    A 5ª edição exige B textural *imediatamente abaixo* do A ou E, e a API do
    SmartSolos, que implementa a 5ª, devolve CAMBISSOLO para um perfil com Bi
    logo abaixo do A e Bt fundo. A 6ª testa Argissolos antes de Cambissolos,
    mas é internamente inconsistente sobre a posição do Bt — "subjacente a
    [...] nos primeiros 200 cm" no Cap. 5 (p. 125), "imediatamente abaixo" na
    Definição do Cap. 3 (p. 97) —, e a base da 6ª deixa o caso indeterminado
    (2026-10-15). Não há comportamento de referência para a 6ª.
    """
    print("\ndivergência de edição: Cambissolo × Argissolo")
    p = Perfil("SINTETICO_Bi_sobre_Bt_fundo", [
        Horizonte("A", 0, 20,
                  {"ARGILA": 120, "SILTE": 100, "AREIA_GROS": 400, "AREIA_FINA": 380}),
        Horizonte("Bi", 20, 60,
                  {"ARGILA": 150, "SILTE": 100, "AREIA_GROS": 400, "AREIA_FINA": 350}),
        Horizonte("BC", 60, 105,
                  {"ARGILA": 200, "SILTE": 100, "AREIA_GROS": 350, "AREIA_FINA": 350}),
        Horizonte("Bt", 105, 160,
                  {"ARGILA": 400, "SILTE": 100, "AREIA_GROS": 250, "AREIA_FINA": 250}),
    ])
    c = cotejar(p)
    confere(c.sob_5a.classe == "CAMBISSOLO",
            "sob a 5ª edição o perfil é CAMBISSOLO, como devolve a API")
    # 2026-10-15: a 6ª edição não decide o caso ('subjacente a' no Cap. 5,
    # 'imediatamente abaixo' no Cap. 3). Antes o teste exigia ARGISSOLO
    # concluído, fixando como norma uma das leituras.
    alcancaveis_6 = {c.sob_6a.classe, *c.sob_6a.alcancaveis} - {None}
    confere(not c.sob_6a.conclusivo
            and {"ARGISSOLO", "CAMBISSOLO"} <= alcancaveis_6,
            "sob a 6ª edição o perfil fica indeterminado entre ARGISSOLO e "
            f"CAMBISSOLO — a norma vigente não decide (obtido {c.sob_6a.classe}, "
            f"alcançáveis {c.sob_6a.alcancaveis})")
    confere(c.divergem or not c.ambas_conclusivas,
            "o cotejo registra a diferença, marcada como não conclusiva")


def teste_contencao_5ed() -> None:
    """Contenção sobre o conjunto curado usando a base de produção do NS5.

    Os rótulos do conjunto são da 5ª edição, e esta é a base da 5ª edição —
    é este, e não o cotejo contra a 6ª, o teste de contenção pertinente.
    """
    import unicodedata

    def limpo(t):
        return "".join(c for c in unicodedata.normalize("NFD", (t or "").upper())
                       if unicodedata.category(c) != "Mn")

    print("\npropriedade de contenção sob a 5ª edição (base de produção)")
    arquivos = sorted(
        a for a in PYKKA7.glob("*/json/*.json") if not a.name.endswith("_all.json")
    )
    violacoes = []
    for arquivo in arquivos:
        for p in carregar_json(arquivo):
            registrado = limpo(p.classe_registrada[0])
            if not registrado or registrado == "UNKNOWN":
                continue
            r = classificar(p, CHAVE_5ED)
            possiveis = {limpo(c) for c in r.alcancaveis + [r.classe or ""]}
            if registrado not in possiveis:
                violacoes.append((p.id_ponto, registrado, r.resumo()))
    confere(True, f"{len(arquivos)} perfis avaliados; "
                  f"{len(violacoes)} classes registradas fora do conjunto alcançável")
    for v in violacoes:
        print(f"       ⚠️ {v[0]}: registrado {v[1]}, derivado {v[2]}")


def teste_glei_precedente_nao_imediato() -> None:
    """Condição (b): o glei basta estar **acima**; o A e o E, **imediatamente**.

    🚨 Oitavo defeito (2026-10-11), achado por leitura da norma ao lado do
    código, e não por perfil do conjunto curado. A frase é a mesma nas duas
    edições: "quando precedidos de horizonte glei ou situados imediatamente
    abaixo do horizonte A ou E ou de outro horizonte que apresente cores
    pálidas…" (5ª ed., p. 104 e 261; 6ª ed., p. 269). O advérbio
    "imediatamente" governa A, E e o horizonte pálido — **não o glei**. A
    implementação testava o glei só no horizonte logo acima do plíntico, como
    se o advérbio valesse para os quatro termos.

    Nenhum perfil do conjunto curado cai no caso, por isso a contenção de
    100% não o denunciava. Os dois perfis abaixo são sintéticos: um expõe o
    defeito, o outro protege a parte estrita da regra, para que a correção do
    glei não afrouxe o A e o E junto.
    """
    print("\ncondição (b) — glei precedente, A e E imediatos (oitavo defeito)")
    b5 = PREDICADOS["plíntico até 200 cm em posição diagnóstica (5ª ed.)"]
    b6 = PREDICADOS["plíntico até 200 cm em posição diagnóstica (6ª ed.)"]

    def cor(matiz, valor, croma):
        return {"COR_UMIDA_MATIZ": matiz, "COR_UMIDA_VALOR": valor,
                "COR_UMIDA_CROMA": croma}

    # Glei dois horizontes acima do plíntico, com um C avermelhado no meio.
    # O C não é A, E, glei nem pálido: só o glei distante pode satisfazer (b).
    glei_distante = Perfil("sintetico-glei-distante", [
        Horizonte("A", 0, 15, cor("2.5YR", 3, 4)),
        Horizonte("Cg", 15, 50, cor("5Y", 6, 1)),
        Horizonte("C", 50, 90, cor("2.5YR", 4, 6)),
        Horizonte("Cf", 90, 130, cor("10YR", 7, 2)),
    ])
    for nome, pred in (("5ª", b5), ("6ª", b6)):
        valor, detalhe = pred(glei_distante)
        confere(valor is V and "Cg" in detalhe,
                f"{nome} ed.: Cf a 90 cm com glei (Cg) dois horizontes acima "
                f"satisfaz a condição (b) — 'precedidos' não é 'imediatamente' "
                f"(obtido {valor}: {detalhe})")

    # Controle: A dois horizontes acima, sem glei no perfil. Aqui o
    # "imediatamente" vale, e a condição (b) não pode ser satisfeita pelo A.
    a_distante = Perfil("sintetico-a-distante", [
        Horizonte("A", 0, 20, cor("2.5YR", 3, 4)),
        Horizonte("Bt", 20, 80, cor("2.5YR", 4, 6)),
        Horizonte("Btf", 80, 120, cor("10YR", 7, 2)),
    ])
    for nome, pred in (("5ª", b5), ("6ª", b6)):
        valor, detalhe = pred(a_distante)
        confere(valor is F,
                f"{nome} ed.: Btf sob Bt avermelhado, com o A dois horizontes "
                f"acima, NÃO satisfaz pelo A — o A tem de estar imediatamente "
                f"acima (obtido {valor}: {detalhe})")


def teste_estrutura_do_a_chernozemico() -> None:
    """A chernozêmico exige estrutura **moderada ou forte**, não fraca.

    🚨 Nono defeito (2026-10-12), achado na revisão do texto da monografia
    contra a norma, ao conferir o efeito de uma correção do adaptador do
    BDSolos — e não por perfil do conjunto curado. A norma exige "grau de
    desenvolvimento predominantemente moderado ou forte" (5ª ed., item a do
    A chernozêmico; 6ª ed., p. 60-61). O código testava `>= 2`, que na escala
    do contrato (ausente 1, fraca 2, moderada 3, forte 4) aceita **fraca**.

    Nenhum horizonte A do conjunto curado com grau 2 cumpre os demais
    critérios, por isso nenhuma medida mudou. Os perfis abaixo são sintéticos
    e idênticos salvo no grau da estrutura.
    """
    print("\nA chernozêmico — estrutura ao menos moderada (nono defeito)")
    pred = PREDICADOS["horizonte A chernozêmico"]

    def com_grau(grau):
        a = {"COR_UMIDA_VALOR": 2, "COR_UMIDA_CROMA": 2, "V_PERCENT": 80.0,
             "C_ORG": 20.0, "ESTRUTURA_GRAU": grau}
        return Perfil(f"sintetico-a-grau-{grau}", [
            Horizonte("A", 0, 30, a),
            Horizonte("C", 30, 80, {}),
        ])

    for grau, esperado, rotulo in ((2, F, "fraca"), (3, V, "moderada"),
                                   (4, V, "forte"), (1, F, "ausente")):
        valor, detalhe = pred(com_grau(grau))
        confere(valor is esperado,
                f"estrutura {rotulo} (grau {grau}) → {esperado} "
                f"(obtido {valor}: {detalhe})")


def teste_neossolo_plintico_pelo_capitulo() -> None:
    """A exclusão do plíntico nos Neossolos segue o Cap. 3, não a chave.

    🚨 Décimo defeito (2026-10-14), achado na revisão da seção 4.2.1 da
    monografia. A regra da 5ª excluía o plíntico só "dentro de 40 cm" (chave,
    p. 111-112); a definição (Cap. 3, p. 96) exclui também "dentro de 150 cm
    [...] se imediatamente abaixo de horizontes A ou E ou se precedido de
    horizontes de coloração pálida". Um A seguido de plíntico a 50-150 cm saía
    NEOSSOLO sob a 5ª e PLINTOSSOLO sob a 6ª — diferença de modelagem que a
    Camada de Versão leria como normativa. Entre 150 e 200 cm a norma diverge
    de si mesma (Cap. 3 × Cap. 12), e o núcleo devolve indeterminado.

    Nenhum perfil do conjunto curado cai no caso; os perfis são sintéticos.
    """
    print("\nNeossolos: exclusão do plíntico pelo capítulo (décimo defeito)")
    pred = PREDICADOS["plíntico em posição que exclui o Neossolo (5ª ed.)"]

    def horizonte(simbolo, sup, inf, matiz, valor, croma, c_org):
        return Horizonte(simbolo, sup, inf, {
            "COR_UMIDA_MATIZ": matiz, "COR_UMIDA_VALOR": valor,
            "COR_UMIDA_CROMA": croma, "ARGILA": 200, "SILTE": 150,
            "AREIA_GROS": 350, "AREIA_FINA": 300, "C_ORG": c_org,
            "V_PERCENT": 30, "ESTRUTURA_GRAU": 2, "CTC": 8})

    def perfil_com_plintico_a(cm):
        return Perfil(f"sintetico-plintico-{cm}cm-sob-A", [
            horizonte("A", 0, cm, "2.5YR", 5, 4, 5),
            horizonte("Cf", cm, cm + 60, "10YR", 7, 2, 1),
            horizonte("C", cm + 60, cm + 110, "2.5YR", 4, 6, 1),
        ])

    for cm, esperado_pred, esperado_5 in ((50, V, "PLINTOSSOLO"),
                                          (140, V, "PLINTOSSOLO"),
                                          (250, F, "NEOSSOLO")):
        p = perfil_com_plintico_a(cm)
        valor, detalhe = pred(p)
        r5 = classificar(p, CHAVE_5ED)
        r6 = classificar(p, CHAVE_6ED)
        confere(valor is esperado_pred and r5.classe == esperado_5
                and r5.conclusivo and r6.classe == esperado_5,
                f"plíntico a {cm} cm sob o A → {esperado_5} nas duas edições "
                f"(5ª: {r5.classe}, 6ª: {r6.classe}; predicado {valor}: "
                f"{detalhe})")

    p = perfil_com_plintico_a(170)
    valor, detalhe = pred(p)
    r5 = classificar(p, CHAVE_5ED)
    confere(valor is I and not r5.conclusivo
            and "NEOSSOLO" in r5.alcancaveis,
            "plíntico a 170 cm sob o A → indeterminado na 5ª: o Cap. 3 não "
            "exclui, o Cap. 12 exclui, e a norma não decide "
            f"(predicado {valor}; 5ª: {r5.classe}, alcançáveis "
            f"{r5.alcancaveis})")

    controle = Perfil("sintetico-plintico-sob-C-avermelhado", [
        horizonte("A", 0, 30, "2.5YR", 5, 4, 5),
        horizonte("C", 30, 100, "2.5YR", 4, 6, 1),
        horizonte("Cf", 100, 160, "10YR", 7, 2, 1),
    ])
    valor, detalhe = pred(controle)
    confere(valor is F,
            "controle: plíntico a 100 cm sob C avermelhado não exclui o "
            f"Neossolo — a correção não afrouxa a posição ({valor}: {detalhe})")


def teste_identificacao_monotonica() -> None:
    """Medir um atributo ausente não pode tirar a classe do conjunto alcançável.

    🚨 Décimo primeiro defeito (2026-10-14), achado na revisão da seção 4.2.4
    da monografia. A identificação de horizonte era binária: o símbolo
    propunha e o dado só vetava quando presente; faltando o dado, o horizonte
    era **aceito**. Um `Btf` sem cor concluía PLINTOSSOLO, e medir a cor
    (avermelhada, sem mosqueado) levava a ARGISSOLO — fora do conjunto
    alcançável. Agora a falta do dado que poderia vetar deixa a identificação
    indeterminada. Os horizontes abertos do PYKKA7 recebem a profundidade
    observada nas fichas (`dados/pykka7_profundidade_observada.json`), sem a
    qual RN_042 e RN_044 perderiam o plíntico por um defeito de representação.
    """
    print("\nidentificação monotônica: ausência de dado não afirma (11º defeito)")

    def horizonte(simbolo, sup, inf, cor, argila):
        d = {"ARGILA": argila, "SILTE": 150, "AREIA_GROS": 350,
             "AREIA_FINA": 300, "C_ORG": 5, "V_PERCENT": 30,
             "ESTRUTURA_GRAU": 2, "CTC": 8}
        if cor:
            d.update({"COR_UMIDA_MATIZ": cor[0], "COR_UMIDA_VALOR": cor[1],
                      "COR_UMIDA_CROMA": cor[2]})
        return Horizonte(simbolo, sup, inf, d)

    def perfil(cor):
        return Perfil("sintetico-Btf", [
            horizonte("A", 0, 20, ("7.5YR", 4, 3), 150),
            horizonte("Btf", 20, 80, cor, 380),
            horizonte("BC", 80, 130, ("2.5YR", 4, 6), 360),
        ])

    inicial = classificar(perfil(None), CHAVE_5ED)
    conjunto = {inicial.classe, *inicial.alcancaveis} - {None}
    confere(not inicial.conclusivo and "PLINTOSSOLO" in conjunto,
            "Btf sem cor: não conclui — PLINTOSSOLO fica alcançável, não "
            f"afirmado (obtido {inicial.classe}, alcançáveis "
            f"{inicial.alcancaveis})")
    for rotulo, cor in (("avermelhada sem mosqueado", ("2.5YR", 4, 8)),
                        ("clara", ("10YR", 7, 2))):
        medido = classificar(perfil(cor), CHAVE_5ED)
        confere(medido.classe in conjunto,
                f"cor medida {rotulo} → {medido.classe}, que estava no "
                f"conjunto alcançável inicial {sorted(conjunto)}")

    for arquivo, esperado_min in (("RN/json/GeoTab_RN_042_Santo_Antonio.json", 40),
                                  ("RN/json/GeoTab_RN_044_Mossoro.json", 15)):
        p = carregar_json(PYKKA7 / arquivo)[0]
        btf = next(h for h in p.horizontes if h.simbolo == "Btf")
        confere(btf.espessura_minima == esperado_min
                and "plíntico" in tipos_de(p, btf),
                f"{p.id_ponto.split('_', 1)[1]}: Btf aberto com {esperado_min} cm "
                "observados na ficha mantém o plíntico (espessura mínima "
                f"{btf.espessura_minima})")

    aberto_curto = Horizonte("Btf", 100, 10000.0,
                             {"COR_UMIDA_MATIZ": "10YR", "COR_UMIDA_VALOR": 7,
                              "COR_UMIDA_CROMA": 2})
    aberto_curto.limite_inf_observado = 110
    p = Perfil("sintetico-Btf-aberto-curto", [
        horizonte("A", 0, 100, ("7.5YR", 4, 3), 150), aberto_curto])
    confere("plíntico" not in tipos_de(p, aberto_curto)
            and "plíntico" in {i.tipo for i in identificar(p) if i.indeterminada},
            "Btf aberto com só 10 cm observados: plíntico pendente, nem "
            "afirmado nem vetado — o horizonte continua")


def teste_requisitos_argissolos_e_luvissolos_6ed() -> None:
    """Requisitos (a) e (b) dos Argissolos; posição do Bt dos Luvissolos na 6ª.

    🚨 Décimo segundo defeito (2026-10-15): a Definição dos Argissolos (Cap. 3;
    5ª p. 87, 6ª p. 97) exige que plíntico — e, na 6ª, concrecionário e
    litoplíntico — e glei não estejam acima nem coincidam com a parte
    superficial do B textural. Nenhuma base o implementava. E os Luvissolos
    da 6ª têm a mesma inconsistência dos Argissolos ("subjacente a" na chave
    e no Cap. 11, "imediatamente abaixo" na Definição do Cap. 3, p. 105):
    agora indeterminados quando o Bt não é adjacente mas está nos 200 cm.
    """
    print("\nArgissolos: requisitos da Definição; Luvissolos da 6ª: posição do Bt")
    r5 = PREDICADOS["requisitos (a) e (b) da Definição dos Argissolos (5ª ed.)"]
    r6 = PREDICADOS["requisitos (a) e (b) da Definição dos Argissolos (6ª ed.)"]

    def h(simbolo, sup, inf, matiz="7.5YR", valor=4, croma=4, **extra):
        d = {"COR_UMIDA_MATIZ": matiz, "COR_UMIDA_VALOR": valor,
             "COR_UMIDA_CROMA": croma, "ARGILA": extra.pop("argila", 200)}
        d.update(extra)
        return Horizonte(simbolo, sup, inf, d)

    casos = (
        ("plíntico acima do Bt", [h("A", 0, 20, argila=150),
                                  h("Bf", 20, 40, "10YR", 7, 2),
                                  h("Bt", 40, 100, argila=400)], F, F),
        ("plíntico abaixo do topo do Bt", [h("A", 0, 20, argila=150),
                                           h("Bt", 20, 80, argila=400),
                                           h("Btf", 80, 120, "10YR", 7, 2,
                                             argila=400)], V, V),
        ("concrecionário acima do Bt (só a 6ª o lista)",
         [h("A", 0, 20, argila=150), h("Bc", 20, 40),
          h("Bt", 40, 100, argila=400)], V, F),
        ("glei acima do Bt", [h("A", 0, 20, argila=150),
                              h("Bg", 20, 40, "5Y", 6, 1),
                              h("Bt", 40, 100, argila=400)], F, F),
    )
    for nome, hs, esperado5, esperado6 in casos:
        p = Perfil("sintetico-" + nome, hs)
        v5, v6 = r5(p)[0], r6(p)[0]
        confere(v5 is esperado5 and v6 is esperado6,
                f"{nome}: 5ª {esperado5}, 6ª {esperado6} (obtido {v5}, {v6})")

    luv6 = next(r for r in CHAVE_6ED if r.classe == "LUVISSOLO")
    luv5 = next(r for r in CHAVE_5ED if r.classe == "LUVISSOLO")
    bt = dict(argila=400, ATIVIDADE_ARGILA=40, V_PERCENT=80)
    for nome, hs, esperado6, esperado5 in (
        ("Bt imediatamente abaixo do A", [h("A", 0, 20, argila=150),
                                          h("Bt", 20, 80, **bt)], V, V),
        ("A–Bi–Bt, Bt a 60 cm", [h("A", 0, 20, argila=150),
                                 h("Bi", 20, 60, argila=180),
                                 h("Bt", 60, 120, **bt)], I, F),
        ("A–Bi–Bt, Bt a 250 cm", [h("A", 0, 20, argila=150),
                                  h("Bi", 20, 250, argila=180),
                                  h("Bt", 250, 300, **bt)], F, F),
    ):
        p = Perfil("sintetico-luvissolo-" + nome, hs)
        v6 = avaliar(luv6.condicao, p).valor
        v5 = avaliar(luv5.condicao, p).valor
        confere(v6 is esperado6 and v5 is esperado5,
                f"Luvissolo, {nome}: 6ª {esperado6}, 5ª {esperado5} "
                f"(obtido {v6}, {v5})")


def teste_explicador() -> None:
    print("\nexplicador de divergências (abdução contrastiva, §4.3)")
    from .explicador import explicar, valor_que_inverte
    from .perfil import carregar_json as _carregar

    confere(valor_que_inverte(36, ">=", 360) == 360,
            "predicado não estrito é satisfeito na fronteira")
    confere(valor_que_inverte(5, ">", 5) > 5 and
            valor_que_inverte(5, ">", 5) < 5.000001,
            "predicado estrito recebe o menor passo acima do limiar")
    confere(valor_que_inverte(9, "<", 5) < 5,
            "predicado estrito de menor recebe o passo abaixo do limiar")

    # Sem divergência — a classe registrada é a derivada ou continua
    # alcançável (incompletude) —, não há o que explicar. Nos 94 perfis
    # curados a classe registrada só fica fora do conjunto alcançável em
    # `GeoTab_RN_019_Apodi`, desde o 16º defeito (2026-10-17): o rótulo
    # CHERNOSSOLO RÊNDZICO segue a leitura do SmartSolos, que não aplica o
    # terço do item (e) do A chernozêmico (Ak1 de 18 cm em A+C de 65 cm);
    # o núcleo segue a norma, por decisão do usuário. Divergência esperada.
    arquivos = [a for a in sorted(PYKKA7.rglob("*.json"))
                if not a.name.endswith("_all.json")]
    perfis = [p for arquivo in arquivos for p in _carregar(arquivo)]
    divergentes = {p.id_ponto for p in perfis if p.classe_registrada[0]
                   and explicar(p, p.classe_registrada[0]) is not None}
    confere(divergentes == {"GeoTab_RN_019_Apodi"},
            "dos 94 perfis curados, só RN_019 é divergente (leitura do "
            f"SmartSolos sobre a espessura do A chernozêmico); obtido {sorted(divergentes)}")

    # Erro injetado: a hipótese verdadeira está na lista, verificada, e o
    # deslocamento decimal que a desfaz é reconhecido como típico.
    from .injecao import gerar
    from .avaliador import classificar as _classificar
    inj = next(i for p in perfis for i in gerar([p]).injecoes)
    exp = explicar(inj.perfil, inj.classe)
    confere(exp is not None and exp.origem in (1, 2),
            f"injeção em {inj.atributo}({inj.original.horizontes[inj.indice].simbolo})"
            f" de {inj.original.id_ponto} produz divergência explicável")
    alvo = [h for h in exp.hipoteses
            if h.indice == inj.indice and h.atributo == inj.atributo]
    confere(len(alvo) == 1 and alvo[0].tipico is not None,
            "a hipótese sobre o atributo injetado está na lista e é típica")
    from .explicador import alterar
    confere(all(_classificar(alterar(inj.perfil, h.indice, h.atributo,
                                     h.valor_proposto)).classe == inj.classe
                for h in exp.hipoteses),
            "toda hipótese listada restabelece a classe ao ser reexecutada")


def teste_b_sem_sufixo_legivel() -> None:
    print("\nB sem sufixo legível (notação anterior a 1988, decisão de 2026-10-15)")
    from .horizontes import b_sem_sufixo_legivel, sem_b_diagnostico
    confere(all(b_sem_sufixo_legivel(gs.analisa(s))
                for s in ("B", "B1", "B21", "2B", "BW2")),
            "B, B1, B21, 2B e BW2 não dizem o tipo de B")
    confere(not any(b_sem_sufixo_legivel(gs.analisa(s))
                    for s in ("BA", "BC", "AB", "Bt", "Bcn", "B/A")),
            "transicionais, mesclados e B com sufixo ficam de fora")

    def perfil_b(simbolo):
        return Perfil("sintetico-b-antigo", [
            Horizonte("A1", 0, 20, {"ARGILA": 300}),
            Horizonte(simbolo, 20, 150, {"ARGILA": 450}),
        ])
    antigo = perfil_b("B21")
    res = classificar(antigo, CHAVE_5ED)
    alc = set(res.alcancaveis) | ({res.classe} if res.classe else set())
    confere("LATOSSOLO" in alc and res.classe != "NEOSSOLO",
            f"A1–B21: Latossolo alcançável e Neossolo não afirmado ({res.resumo()})")
    confere(sem_b_diagnostico(antigo)[0] is I,
            "A1–B21: 'sem B diagnóstico' é indeterminado, e não verdadeiro")
    moderno = perfil_b("Bw")
    confere(classificar(moderno, CHAVE_5ED).classe != "NEOSSOLO"
            and sem_b_diagnostico(moderno)[0] is F,
            "A1–Bw continua identificando B latossólico")


def teste_prefixo_romano() -> None:
    print("\nprefixo de descontinuidade em algarismo romano (14º defeito)")
    from .horizontes import principal, tipos_de
    p = Perfil("sintetico-romano", [
        Horizonte("A1", 0, 20, {"ARGILA": 150}),
        Horizonte("IIBt1", 20, 80, {"ARGILA": 450}),
    ])
    bt = p.horizontes[1]
    confere(principal(bt) == "B",
            f"IIBt1 tem principal B (leu {principal(bt)!r})")
    confere("B textural" in tipos_de(p, bt),
            "IIBt1 propõe B textural, como 2Bt1")


def teste_niveis_2_e_3() -> None:
    print("\n2º e 3º níveis das cinco ordens (SiBCS 5ª ed.)")
    from .perfil import matiz_numerico
    from .niveis5 import SUBORDENS, coincide
    from .avaliacao_niveis import casos_curados, desfecho_niveis
    confere([matiz_numerico(m) for m in ("10R", "2.5YR", "5YR", "7,5YR", "10YR", "N")]
            == [10.0, 12.5, 15.0, 17.5, 20.0, None],
            "matiz Munsell vira número na escala R < YR < Y")
    confere(coincide("FERRIHUMILÚVICO", "FERRI-HUMILÚVICO")
            and coincide("LUVISSOLO HÁPLICO Órtico", "Órtico")
            and not coincide("Distrocoeso", "Distrófico"),
            "comparação de rótulo tolera grafia, não troca de classe")

    sem_o = Perfil("sintetico-sem-O", [
        Horizonte("A", 0, 20, {"C_ORG": 15}), Horizonte("Bi", 20, 80, {})])
    r = classificar(sem_o, SUBORDENS["CAMBISSOLO"][:1])
    confere(r.classe is None and not r.alcancaveis,
            "sem horizonte O, a subordem Hístico é refutada, e não indeterminada")

    from .niveis5 import normaliza
    ordens = {normaliza(o) for o in SUBORDENS}
    casos = [c for c in casos_curados() if normaliza(c[1][0]) in ordens]
    divergem = [c[0] for c in casos
                if desfecho_niveis(c[1][:3], c[2][:3])[1] == "diverge"]
    confere(not divergem, f"nenhum perfil curado diverge nos níveis 1 a 3 {divergem[:3]}")
    fora = [c[0] for c in casos
            if desfecho_niveis(c[1][:3], c[2][:3])[1] == "não conclui, rótulo fora"]
    # 20º defeito (2026-10-17): o Bw de 35 cm do PE_032 é o último horizonte e
    # só alcança 50 cm com o BA; a ordem deixa de ser concluída e o caso do
    # GDE_GRUPO não atualizado deixa de aparecer no 3º nível.
    confere(fora == [],
            f"nenhum perfil curado tem rótulo fora até o 3º nível: {fora}")

    from .niveis5_subgrupos import SUBGRUPOS, verificar_traducao
    confere(not verificar_traducao() and sum(len(v) for v in SUBGRUPOS.values()) == 448,
            "as 100 definições de subgrupo batem com a tradução; 448 subgrupos")
    quarto = sorted((c[0], desfecho_niveis(c[1], c[2])[1]) for c in casos
                    if desfecho_niveis(c[1], c[2])[0] == 3
                    and desfecho_niveis(c[1], c[2])[1] in ("diverge", "não conclui, rótulo fora"))
    confere([i for i, _ in quarto] == ["GeoTab_PE_017_Barreiros",
                                        "GeoTab_PE_034_Abreu_e_Lima",
                                        "GeoTab_PE_037_Ipojuca"],
            f"no 4º nível, só os três casos de fronteira registrados: {quarto}")


def teste_contencao_por_ablacao() -> None:
    print("\ncontenção sob ablação de atributo (Avaliador Parcial, §4.2.4)")
    from .avaliacao_parcial import ablacao
    from .explicador import ATRIBUTOS_ANALITICOS, ATRIBUTOS_COR
    from .perfil import carregar_json as _carregar
    arquivos = [a for a in sorted(PYKKA7.rglob("*.json"))
                if not a.name.endswith("_all.json")]
    perfis = [p for arquivo in arquivos for p in _carregar(arquivo)]

    # Décimo terceiro defeito: sem o croma úmido, o A chernozêmico era
    # refutado em vez de indeterminado.
    pe020 = next(p for p in perfis if p.id_ponto == "GeoTab_PE_020_Macaparana")
    linha = ablacao([pe020], {"croma": ("COR_UMIDA_CROMA",)})[0]
    confere(linha["contem"] and "CHERNOSSOLO" in linha["alcancaveis"],
            "PE_020 sem COR_UMIDA_CROMA mantém CHERNOSSOLO alcançável")

    linhas = ablacao(perfis, {a: (a,) for a in ATRIBUTOS_ANALITICOS + ATRIBUTOS_COR})
    violadas = [(l["perfil"], l["unidade"]) for l in linhas if not l["contem"]]
    confere(not violadas,
            f"{len(linhas)} remoções de atributo isolado; contenção violada em "
            f"{len(violadas)} {violadas[:3]}")


def teste_textura_arenosa_pela_norma() -> None:
    """Textura arenosa do 1º nível pela definição da norma (2026-10-16).

    SiBCS 5ª ed., Cap. 1, p. 46: "teor de areia menos teor de argila > 700 g
    kg-1". Até 2026-10-16, `_arenoso` (exclusão textural dos Gleissolos)
    aproximava por areia ≥ 700 e argila ≤ 150, e aceitava como arenoso o que a
    norma não aceita. Decisão do usuário: alinhar à norma; o 1º nível e os
    subgrupos (`ARENOSA`, em `perfil.py`) passam a usar a mesma fórmula.
    """
    from .horizontes import _arenoso
    from .perfil import _derivados
    print("\ntextura arenosa pela definição da norma (p. 46)")

    def h(areia_grossa, areia_fina, argila):
        return Horizonte("C", 0, 50, {"AREIA_GROS": areia_grossa,
                                      "AREIA_FINA": areia_fina,
                                      "ARGILA": argila})

    confere(_arenoso(h(400, 300, 150)) is False,
            "areia 700, argila 150 (diferença 550): não é arenosa — a "
            "aproximação antiga aceitava")
    confere(_arenoso(h(500, 350, 150)) is False,
            "areia 850, argila 150 (diferença 700, não maior): não é arenosa")
    confere(_arenoso(h(500, 360, 140)) is True,
            "areia 860, argila 140 (diferença 720): é arenosa")
    confere(_arenoso(Horizonte("C", 0, 50, {"ARGILA": 100})) is None,
            "sem areia, indeterminado — nunca falso")
    casos = (h(400, 300, 150), h(500, 350, 150), h(500, 360, 140))
    confere(all(_arenoso(x) == bool(_derivados(x).get("ARENOSA")) for x in casos),
            "1º nível e subgrupos (ARENOSA) usam a mesma fórmula")


def teste_simbolo_antigo_com_mais_de_uma_leitura() -> None:
    """Símbolo antigo com mais de uma tradução — opção (b), 2026-10-16.

    Larach et al. (1988), Anexo 1: o `B1` de 1962 é hoje `BA` **ou** `BE`, e o
    sentinela não traduz o que não é unívoco. O `B1t` ficava sem leitura, o
    núcleo não o enxergava e o B textural "imediatamente abaixo do A" falhava:
    8 das 13 divergências de 1º nível das fichas originais vinham disso.
    Decisão do usuário: quando as traduções concordam na letra principal e nos
    sufixos (`BAt`/`BEt`), o tipo vale; quando discordam (`A3g` → `ABg`/`EBg`),
    os tipos que alguma leitura propõe ficam pendentes.
    """
    from .horizontes import identificar, leitura_atual, principal
    print("\nsímbolo antigo com mais de uma leitura (opção b)")

    confere(gs.moderniza("B1t") is None and leitura_atual("B1t") == "BAt",
            "B1t: o sentinela não traduz; as leituras BAt/BEt concordam e a "
            "primeira é usada")
    confere(leitura_atual("A3g") is None,
            "A3g: as leituras ABg/EBg discordam na letra principal — sem leitura")
    confere(leitura_atual("B2t") == "Bt" and leitura_atual("Bt1") is None,
            "símbolo de tradução única e símbolo atual não mudam")

    p = Perfil("sintetico-B1t", [
        Horizonte("A1", 0, 20, {"ARGILA": 150}),
        Horizonte("B1t", 20, 40, {"ARGILA": 350}),
        Horizonte("B2t", 40, 100, {"ARGILA": 400})])
    b1 = p.horizontes[1]
    ids = [i for i in identificar(p) if i.horizonte is b1]
    confere(principal(b1) == "B" and any(i.tipo == "B textural" and i.valida for i in ids),
            "B1t é B textural válido, e sua letra principal é B")

    q = Perfil("sintetico-A3g", [
        Horizonte("A1", 0, 20, {}), Horizonte("A3g", 20, 40, {}),
        Horizonte("Bg", 40, 100, {})])
    a3 = q.horizontes[1]
    ids = [i for i in identificar(q) if i.horizonte is a3]
    confere(ids and all(i.indeterminada for i in ids)
            and any(i.tipo == "glei" for i in ids),
            "A3g: o glei que as leituras propõem fica pendente, nunca afirmado")

    from .avaliador import _acima_ignorando_transicionais
    from .horizontes import principais_possiveis
    confere(principais_possiveis(a3) == {"A", "E"},
            "A3g admite A ou E como letra principal")
    confere(_acima_ignorando_transicionais(q, q.horizontes[2]) is q.horizontes[0],
            "A3g é transicional nas duas leituras e é saltado: o Bg fica "
            "imediatamente abaixo do A1")

    from . import regras as rr
    from .avaliador import _avaliar_por_leitura, _variantes_de_leitura
    tem_e = rr.Existe(onde=rr.Seletor(principal="E"))
    variantes = _variantes_de_leitura(q)
    confere(len(variantes) == 2
            and _avaliar_por_leitura(tem_e, q, variantes).valor is I,
            "A3g: 'existe horizonte E' é falso numa leitura (ABg) e verdadeiro "
            "na outra (EBg) — indeterminado, nunca afirmado")
    confere(_variantes_de_leitura(p) == [p],
            "perfil sem leituras discordantes é avaliado uma vez, como antes")

    r = carregar_json(ORIGINAIS / "GeoTab_RN_005_Macau.json")[0]
    confere(classificar(r, CHAVE_5ED).classe == "ARGISSOLO",
            "RN_005 pela ficha original (A1, B1t, B2t, B22t) conclui ARGISSOLO, "
            "como registrado")


def teste_soma_ca_mg_do_acervo() -> None:
    """A soma Ca + Mg do BDSolos chega ao cálculo de S, T e V% (2026-10-16).

    Em 37,4% dos horizontes do BDSolos com dado de Ca/Mg, o laudo traz só a
    soma; o contrato da API pede Ca e Mg separados, e o adaptador a descartava.
    Decisão do usuário: transportá-la fora do contrato (`_CA_MG_TROC`) e usá-la
    quando faltam os valores separados — nunca reparti-la.
    """
    from .perfil import _derivados
    print("\nsoma Ca + Mg do acervo (fora do contrato)")

    def h(**a):
        return Horizonte("Bt", 20, 60, dict(K_TROC=0.03, NA_TROC=0.02, H_TROC=1.5,
                                            AL_TROC=1.2, ARGILA=300, **a))
    so_soma = _derivados(h(_CA_MG_TROC=0.5))
    confere(abs(so_soma["SOMA_BASES"] - 0.55) < 1e-9
            and abs(so_soma["CTC"] - 3.25) < 1e-9
            and abs(so_soma["V_PERCENT"] - 100 * 0.55 / 3.25) < 1e-9,
            "só a soma: S, T e V% calculados a partir dela")
    separados = _derivados(h(CA_TROC=2.0, MG_TROC=1.0, _CA_MG_TROC=99))
    confere(abs(separados["SOMA_BASES"] - 3.05) < 1e-9,
            "Ca e Mg separados têm precedência sobre a soma")
    confere("SOMA_BASES" not in _derivados(h()) or _derivados(h())["SOMA_BASES"] is None,
            "sem Ca, Mg nem soma: S não é calculada")
    confere(_derivados(h(_CA_MG_TROC=0.5)).get("CA_TROC") is None,
            "a soma nunca é repartida entre Ca e Mg")

    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3] / "tools"))
    import agroapi_verify
    limpo = agroapi_verify.limpar({"ID_PONTO": "x", "_corroborado": True,
                                   "HORIZONTES": [{"SIMB_HORIZ": "Bt", "_CA_MG_TROC": 0.5}]})
    confere(limpo["HORIZONTES"] == [{"SIMB_HORIZ": "Bt"}] and "_corroborado" not in limpo,
            "o envio à API descarta os campos fora do contrato")


def teste_a_chernozemico_por_kleene() -> None:
    """15º defeito (2026-10-16): componente presente que reprova decide o A.

    Faltando um componente, o predicado devolvia indeterminado mesmo com outro
    componente presente já reprovando o horizonte. Pela regra de Kleene, a
    conjunção é falsa com um termo falso. A pendência passou a nomear o que
    falta, por horizonte.
    """
    from .horizontes import a_chernozemico
    print("\nA chernozêmico pela regra de Kleene (15º defeito)")

    def perfil(**a):
        base = dict(COR_UMIDA_VALOR=3, COR_UMIDA_CROMA=2, V_PERCENT=80,
                    C_ORG=12, ESTRUTURA_GRAU=3, ARGILA=200)
        base.update(a)
        return Perfil("sintetico-achern", [
            Horizonte("A", 0, 30, {k: v for k, v in base.items() if v is not None}),
            Horizonte("Bi", 30, 80, {"ARGILA": 250})])

    valor, _ = a_chernozemico(perfil())
    confere(valor is V, "todos os componentes aprovam: A chernozêmico")
    valor, detalhe = a_chernozemico(perfil(ESTRUTURA_GRAU=None))
    confere(valor is I and "falta grau de estrutura" in detalhe,
            "só falta a estrutura: indeterminado, e a pendência a nomeia")
    valor, _ = a_chernozemico(perfil(ESTRUTURA_GRAU=None, COR_UMIDA_CROMA=6))
    confere(valor is F,
            "falta a estrutura, mas o croma 6 já reprova: falso, e não indeterminado")
    valor, _ = a_chernozemico(perfil(C_ORG=None, V_PERCENT=40))
    confere(valor is F, "falta o carbono, mas V de 40% já reprova: falso")


def teste_espessura_do_a_chernozemico() -> None:
    """16º defeito (2026-10-17): espessura do A chernozêmico pelo item (e).

    A espessura soma os sub-horizontes A (inclusive AB, AE e AC) que atendem
    os demais itens, e o mínimo segue os quatro ramos da norma (5ª ed., p. 51),
    com o terço do solum. A versão anterior media cada horizonte sozinho
    contra 18 ou 25 cm.
    """
    from .horizontes import a_chernozemico
    print("\nA chernozêmico: espessura pelo item (e) (16º defeito)")
    BOM = dict(COR_UMIDA_VALOR=3, COR_UMIDA_CROMA=2, V_PERCENT=80, C_ORG=12,
               ESTRUTURA_GRAU=3, ARGILA=200)

    def hz(simbolo, sup, inf, **a):
        return Horizonte(simbolo, sup, inf, {**BOM, **a})

    def sub(simbolo, sup, inf):
        return Horizonte(simbolo, sup, inf, {"ARGILA": 300, "COR_UMIDA_VALOR": 5,
                                             "COR_UMIDA_CROMA": 6})

    valor, _ = a_chernozemico(Perfil("sint-ap-ab", [
        hz("Ap", 0, 13), hz("AB", 13, 22), sub("Bi", 22, 50)]))
    confere(valor is V, "Ap 13 + AB 9 = 22 cm, solum 50 (> 16,7 e ≥ 18): soma aprova")
    valor, _ = a_chernozemico(Perfil("sint-ap-fraco", [
        hz("Ap", 0, 10, ESTRUTURA_GRAU=2), hz("A2", 10, 26), hz("A3", 26, 46),
        sub("Bi", 46, 70)]))
    confere(valor is V, "Ap fraco fora da soma; A2 + A3 = 36 cm > 23,3 (PE_020)")
    valor, _ = a_chernozemico(Perfil("sint-terco", [
        hz("A", 0, 18), sub("C", 18, 65)]))
    confere(valor is F, "sem B, A+C de 65 cm: 18 cm não passa de 21,7 (ramo 3)")
    valor, _ = a_chernozemico(Perfil("sint-rocha", [
        hz("A", 0, 12), Horizonte("R", 12, 30, {})]))
    confere(valor is V, "A de 12 cm seguido de R: ramo 1, 10 cm")
    valor, _ = a_chernozemico(Perfil("sint-lacuna", [
        hz("A", 0, 20), Horizonte("C", 20, 10000.0, {"ARGILA": 300})]))
    confere(valor is I, "sem B e C aberto: a norma não decide entre 18 e 25 cm")


def teste_v_do_boletim() -> None:
    """Decisão 2, opção (c) (2026-10-17): V do boletim como complemento e árbitro.

    Sem os componentes, vale o V informado no laudo; com os dois, vale o
    calculado, e, se caem em lados opostos de 50% ou 65%, o que depende do V
    sai indeterminado (caso `BDSolos|797|12674|RS-11`: 64,6% calculado, 65%
    no boletim).
    """
    from . import regras as rr
    from .avaliador import _avaliar_por_leitura, _variantes_de_leitura
    from .perfil import _derivados
    print("\nV do boletim: complemento e árbitro (decisão 2, opção c)")
    BASE = dict(COR_UMIDA_VALOR=3, COR_UMIDA_CROMA=2, C_ORG=12, ESTRUTURA_GRAU=3,
                ARGILA=200, CA_TROC=5.0, MG_TROC=1.46, K_TROC=0.2, NA_TROC=0.1)

    def perfil(**a):
        atr = {**BASE, **a}
        h = Horizonte("A", 0, 30, {k: v for k, v in atr.items() if v is not None})
        h.atributos.update(_derivados(h))
        return Perfil("sint-v", [h, Horizonte("Bi", 30, 80, {"ARGILA": 250})])

    so_boletim = perfil(_V_BOLETIM=80)                     # sem H e Al: sem cálculo
    confere(so_boletim.horizontes[0].get("V_PERCENT") == 80,
            "sem H e Al, vale o V informado no boletim (80%)")
    achern = rr.Derivado(predicado="horizonte A chernozêmico")

    def avalia(p):
        return _avaliar_por_leitura(achern, p, _variantes_de_leitura(p)).valor

    rs11 = perfil(H_TROC=3.5, AL_TROC=0.0, _V_BOLETIM=65)  # 100·6,76/10,26 = 65,9
    confere(rs11.horizontes[0].get("V_PERCENT") > 65 and avalia(rs11) is V,
            "cálculo e boletim do mesmo lado de 65%: decide como antes")
    conflito = perfil(H_TROC=3.9, AL_TROC=0.0, _V_BOLETIM=65)  # 63,4% calculado
    confere(len(_variantes_de_leitura(conflito)) == 2 and avalia(conflito) is I,
            "63,4% calculado e 65% no boletim: A chernozêmico indeterminado, nunca refutado")
    confere(avalia(perfil(H_TROC=3.9, AL_TROC=0.0)) is F,
            "sem V no boletim, o calculado (63,4%) decide: falso")


def teste_concrecionario_nos_neossolos_5ed() -> None:
    """Decisão 3, opção (c) (2026-10-17): concrecionário sem B diagnóstico.

    Pela letra da 5ª (chave, Definição, Cap. 12), só o plíntico exclui o
    Neossolo; pelo Conceito e pela Abrangência dos Plintossolos, o
    concrecionário também. A norma diverge de si mesma: a 5ª não conclui
    Neossolo, e o Plintossolo fica alcançável. A 6ª (p. 227) decide.
    """
    print("\nNeossolos da 5ª: concrecionário sem B diagnóstico (decisão 3)")
    from .horizontes import PREDICADOS

    def perfil(simbolo):
        atr = {"ARGILA": 200, "COR_UMIDA_MATIZ": "10YR", "COR_UMIDA_VALOR": 4,
               "COR_UMIDA_CROMA": 3, "V_PERCENT": 30, "C_ORG": 8, "ESTRUTURA_GRAU": 2}
        return Perfil(f"sint-{simbolo}", [
            Horizonte("A", 0, 20, dict(atr)),
            Horizonte(simbolo, 20, 70, {**atr, "C_ORG": 2}),
            Horizonte("C", 70, 120, {**atr, "C_ORG": 1})])

    pred = PREDICADOS["concrecionário ou litoplíntico em posição de Plintossolo (5ª ed.)"]
    com = perfil("Cc")
    valor, _ = pred(com)
    confere(valor is I, "Cc a 20 cm: a exclusão pelo Conceito fica indeterminada, nunca afirmada")
    r5 = classificar(com, CHAVE_5ED)
    confere(r5.classe != "NEOSSOLO" and "NEOSSOLO" in r5.alcancaveis
            and "PLINTOSSOLO" in (r5.alcancaveis + [r5.classe]),
            f"5ª: Neossolo e Plintossolo alcançáveis (obtido {r5.classe}, {r5.alcancaveis})")
    confere(classificar(com, CHAVE_6ED).classe == "PLINTOSSOLO",
            "6ª: a exclusão está no texto (p. 227) e o perfil é Plintossolo")
    confere(classificar(perfil("C2"), CHAVE_5ED).classe == "NEOSSOLO",
            "sem o sufixo c, a 5ª conclui Neossolo como antes")


def teste_mosqueado_incompleto_nao_veta_plintico() -> None:
    """18º defeito (2026-10-17): mosqueado registrado com cor incompleta.

    Matriz avermelhada com mosqueado claro: plíntico. Sem o croma do
    mosqueado, a cor fica incompleta e o horizonte não pode ser refutado —
    a identificação fica pendente. Sem mosqueado registrado, é ausência
    observada, e o veto vale como antes.
    """
    print("\nPlíntico: mosqueado com cor incompleta não veta (18º defeito)")
    from .horizontes import identificar

    def tipos(**mosq):
        atr = {"COR_UMIDA_MATIZ": "2.5YR", "COR_UMIDA_VALOR": 4, "COR_UMIDA_CROMA": 8,
               "ARGILA": 300, **mosq}
        p = Perfil("sint-18", [Horizonte("A", 0, 20, {"ARGILA": 200}),
                               Horizonte("Btf", 20, 60, atr)])
        return {(i.tipo, i.valida, i.indeterminada) for i in identificar(p)
                if i.horizonte.simbolo == "Btf" and i.tipo == "plíntico"}

    confere(("plíntico", True, False) in tipos(COR_MOSQ_MATIZ_1="10YR", COR_MOSQ_VALOR_1=7,
                                                 COR_MOSQ_CROMA_1=2),
            "mosqueado 10YR 7/2 claro: plíntico identificado")
    pend = tipos(COR_MOSQ_MATIZ_1="10YR", COR_MOSQ_VALOR_1=7)
    confere(any(ind for _, _, ind in pend),
            "mosqueado sem croma: identificação pendente, nunca refutada")
    confere(not any(val or ind for _, val, ind in tipos()),
            "sem mosqueado registrado: ausência observada, o veto vale")


def teste_organico_acima_da_superficie() -> None:
    """19º defeito (2026-10-17): O medido para cima a partir da superfície mineral.

    `O 3-0` é camada de 3 cm acima da superfície mineral. Lida literalmente,
    ficava entre o A e o BA e rompia a adjacência do B ao A.
    """
    print("\nHorizonte orgânico acima da superfície mineral (19º defeito)")
    from .avaliador import _acima_ignorando_transicionais
    from .perfil import de_dicionario
    p = de_dicionario({"ID_PONTO": "sint-19", "HORIZONTES": [
        {"SIMB_HORIZ": "A", "LIMITE_SUP": 0, "LIMITE_INF": 8},
        {"SIMB_HORIZ": "O", "LIMITE_SUP": 3, "LIMITE_INF": 0},
        {"SIMB_HORIZ": "BA", "LIMITE_SUP": 8, "LIMITE_INF": 20},
        {"SIMB_HORIZ": "Bw", "LIMITE_SUP": 20, "LIMITE_INF": 80}]})
    o = next(h for h in p.horizontes if h.simbolo == "O")
    confere((o.limite_sup, o.limite_inf) == (-3, 0) and p.horizontes[0] is o,
            "O 3-0 passa a ocupar de -3 a 0 cm, antes do A")
    bw = next(h for h in p.horizontes if h.simbolo == "Bw")
    confere(_acima_ignorando_transicionais(p, bw).simbolo == "A",
            "o Bw fica imediatamente abaixo do A (o BA é transicional)")


def teste_espessura_do_b_latossolico() -> None:
    """20º defeito (2026-10-17): B latossólico com espessura mínima de 50 cm."""
    print("\nEspessura mínima do B latossólico (20º defeito)")
    from .horizontes import identificar
    from .perfil import de_dicionario

    def estado(hz):
        p = de_dicionario({"ID_PONTO": "sint-20", "HORIZONTES": [
            {"SIMB_HORIZ": s, "LIMITE_SUP": a, "LIMITE_INF": b} for s, a, b in hz]})
        ids = [i for i in identificar(p) if i.tipo == "B latossólico"]
        if all(i.valida for i in ids):
            return "V"
        return "I" if any(i.indeterminada for i in ids) else "F"

    confere(estado([("A", 0, 20), ("Bw", 20, 70), ("C", 70, 100)]) == "V",
            "Bw de 50 cm fechado por C: B latossólico")
    confere(estado([("A", 0, 20), ("Bw", 20, 69), ("C", 69, 100)]) == "F",
            "Bw de 49 cm fechado por C: vetado")
    confere(estado([("A", 0, 20), ("Bw1", 20, 45), ("Bw2", 45, 75), ("C", 75, 90)]) == "V",
            "Bw1 + Bw2 somam 55 cm: B latossólico")
    confere(estado([("A", 0, 20), ("BA", 20, 40), ("Bw", 40, 75), ("C", 75, 90)]) == "I",
            "Bw de 35 cm com BA de 20 cm: pendente (a norma não diz se o BA conta)")
    confere(estado([("A", 0, 20), ("Bw", 20, 50)]) == "I",
            "Bw de 30 cm como último horizonte: pendente (base = coleta)")
    confere(estado([("A", 0, 20), ("Bw", 20, 50), ("C", 70, 90)]) == "I",
            "Bw de 30 cm com lacuna abaixo: pendente")


def teste_cotejo_causas_da_nao_conclusao() -> None:
    """I-1 da auditoria (2026-10-17): o cotejo nomeia a causa da não conclusão.

    Antes, toda não conclusão era "possivelmente de cobertura", e o ramo das
    edições concordantes dizia "a divergência NÃO se explica por edição" em
    perfis sem divergência alguma, só não conclusivos.
    """
    from .edicoes import COBERTURA, EXCLUSIVA
    print("\ncotejo entre edições: causas da não conclusão (I-1)")
    perfis = {p.id_ponto: p for a in sorted(PYKKA7.rglob("*.json"))
              if not a.name.endswith("_all.json") for p in carregar_json(a)}
    c = cotejar(perfis["GeoTab_PE_025_Barreiros"])
    confere(c.causas("6") == {"GLEISSOLO": EXCLUSIVA} and not c.causas("5"),
            "PE_025: a 6ª não conclui por critério em que as bases diferem "
            f"(obtido {c.causas('6')})")
    d = c.diagnostico("GLEISSOLO")
    confere("concluída na 5ª" in d and "cobertura" not in d,
            "PE_025: rótulo válido sob a 5ª, não confirmado sob a 6ª, sem "
            "'cobertura'")
    c = cotejar(perfis["GeoTab_RN_045_Mossoro"])
    confere(c.causas("5").get("VERTISSOLO") == COBERTURA,
            "RN_045: Vertissolo apenas triado — cobertura, não critério novo")
    falsos = [pid for pid, p in perfis.items()
              if "NÃO se explica" in cotejar(p).diagnostico(
                  p.classe_registrada[0] or None)]
    confere(not falsos, "nenhum perfil curado recebe o veredito antigo "
                        f"'NÃO se explica por edição' ({len(falsos)})")
    divergem = sum(1 for p in perfis.values() if cotejar(p).divergem)
    confere(divergem == 5, f"as saídas diferem em 5 dos 94 perfis (§5.4; obtido {divergem})")


def teste_tipicidade_fisicamente_possivel() -> None:
    """I-2 da auditoria (2026-10-17): τ só para deslocamento decimal
    fisicamente possível.

    Na ficha original do `PE_007`, a argila do Bt multiplicada por dez (4.000
    g/kg, impossível) também restabelecia o Argissolo, e a hipótese da argila
    recebia τ = 1. O teste do Explicador (injeção "argila ÷ 10" no `PE_001`)
    impede a correção de exigir também a direção da fronteira reportada.
    """
    from .avaliacao_explicador_real import ORIGINAIS
    from .explicador import explicar
    print("\nfator de tipicidade: plausibilidade e direção (I-2)")
    p = carregar_json(ORIGINAIS / "GeoTab_PE_007_Escada.json")[0]
    e = explicar(p, "ARGISSOLO")
    tip = {h.atributo: h.tipico for h in e.hipoteses}
    confere(tip.get("MG_TROC") == "÷10",
            "Mg do Bt 17 → 1,7: deslocamento decimal típico (÷10)")
    confere(tip.get("ARGILA") is None,
            f"argila do Bt: ×10 daria 4.000 g/kg, fora da faixa física — sem τ (obtido {tip.get('ARGILA')})")
    confere(tip.get("H_TROC") == "×10",
            "H do Bt 3,1 → 31: possível e na direção da fronteira (×10)")


def teste_registro_de_curadoria_classificado() -> None:
    """D-2 da auditoria (2026-10-17): a classificação manual do registro de
    curadoria cobre todo perfil com atributo alterável corrigido."""
    import json
    from .avaliacao_explicador_real import ALTERAVEIS, ERROS_DESCRITOS
    print("\nregistro de curadoria classificado à mão (Acerto@k estrito, D-2)")
    dados = json.loads(ERROS_DESCRITOS.read_text(encoding="utf-8"))["perfis"]
    esperados = set()
    for a in sorted(ORIGINAIS.glob("*.json")):
        it = json.loads(a.read_text(encoding="utf-8"))["items"][0]
        if any(x["natureza"] in ("valor corrigido", "omitido na curadoria")
               and x["campo"] in ALTERAVEIS for x in it["_ALTERACOES"]):
            esperados.add(a.stem)
    confere(set(dados) == esperados,
            f"os {len(esperados)} perfis com atributo corrigido estão classificados")
    confere(all({tuple(x) for x in v["erro"]} <= {tuple(x) for x in v["corrigidos"]}
                for v in dados.values()),
            "todo erro descrito é um atributo de fato corrigido")
    confere(dados["GeoTab_PE_007_Escada"]["erro"] == [[2, "MG_TROC"]],
            "PE_007: a nota descreve o Mg do Bt como erro")


def teste_glei_em_solo_arenoso_nos_neossolos_5ed() -> None:
    """21º defeito (2026-10-17): o glei só exclui o Neossolo da 5ª em
    condição diagnóstica para Gleissolos (Cap. 12, p. 219; Cap. 3, p. 96,
    ressalva da textura areia ou areia franca)."""
    from .avaliacao_versao import h
    print("\nNeossolos da 5ª: glei em solo arenoso (21º defeito)")
    areia = dict(ARGILA=50, SILTE=30, AREIA_GROS=600, AREIA_FINA=320)
    arenoso = Perfil("sint-glei-arenoso", [
        h("A", 0, 20, "10YR", 4, 1, **areia),
        h("Cg1", 20, 100, "5Y", 6, 1, **areia),
        h("Cg2", 100, 210, "5Y", 6, 1, **areia)])
    r5 = classificar(arenoso, CHAVE_5ED)
    confere(r5.classe == "NEOSSOLO",
            f"glei em solo arenoso: a 5ª chega ao Neossolo, como a 6ª (obtido {r5.resumo()})")
    argiloso = Perfil("sint-glei-argiloso", [
        h("A", 0, 20, "10YR", 4, 1, ARGILA=350),
        h("Cg1", 20, 100, "5Y", 6, 1, ARGILA=400)])
    r5 = classificar(argiloso, CHAVE_5ED)
    confere(r5.classe == "GLEISSOLO" and "NEOSSOLO" not in r5.alcancaveis,
            f"glei em solo argiloso: Gleissolo, e o Neossolo segue refutado (obtido {r5.resumo()})")


def teste_b_nitico_por_kleene() -> None:
    """22º defeito (2026-10-18): falta de argila não refuta o B nítico."""
    print("\nB nítico em três valores (22º defeito)")
    from .horizontes import identificar, relacao_textural
    from .perfil import Perfil

    def nitico(*hz):
        p = Perfil("sint-21", [Horizonte(s, a, b, at) for s, a, b, at in hz])
        ids = [i for i in identificar(p) if i.tipo == "B nítico"]
        if not ids:
            return "F"
        return "V" if any(i.valida for i in ids) else "I"

    cer = {"CEROSIDADE_GRAU": 3, "CEROSIDADE_QUANTIDADE": 2}
    confere(nitico(("A", 0, 20, {"ARGILA": 450}), ("Bt", 20, 80, {"ARGILA": 500, **cer})) == "V",
            "Bt argiloso com cerosidade comum e moderada e RT 1,1: B nítico")
    confere(nitico(("A", 0, 20, {"ARGILA": 450}), ("Bt", 20, 80, dict(cer))) == "I",
            "argila do Bt não registrada: pendente, e não refutado")
    confere(nitico(("A", 0, 20, {"ARGILA": 450}), ("Bt", 20, 80, {"ARGILA": 500})) == "F",
            "cerosidade não registrada: ausência observada, não identifica (SiBCS 5ª, p. 44)")
    confere(nitico(("A", 0, 20, {"ARGILA": 300}), ("Bt1", 20, 40, {"ARGILA": 600, **cer}),
                   ("Bt2", 40, 80, {**cer})) == "I",
            "relação textural com argila faltando na seção de controle: pendente")
    confere(relacao_textural(Perfil("sint-21b", [Horizonte("A", 0, 20, {"ARGILA": 300}),
                                                 Horizonte("Bt", None, None, {"ARGILA": 500})])) is None,
            "relação textural sem limite superior em nenhum B: None, sem erro")


def main() -> int:

    if not PYKKA7.exists():
        print(f"conjunto curado não encontrado em {PYKKA7}", file=sys.stderr)
        return 2
    for teste in (teste_logica, teste_derivados, teste_relacao_textural,
                  teste_adjacencia_transicional, teste_lacuna_de_descricao,
                  teste_a_chernozemico_estrito,
                  teste_plintico_nao_vem_do_sufixo,
                  teste_empate_da_atividade_da_argila,
                  teste_comparabilidade_das_bases,
                  teste_divergencia_cambissolo_argissolo,
                  teste_condicao_b_dos_plintossolos,
                  teste_rn021_notacao_e_exclusao_textural,
                  teste_glei_30cm_so_na_6ed,
                  teste_glei_precedente_nao_imediato,
                  teste_estrutura_do_a_chernozemico,
                  teste_neossolo_plintico_pelo_capitulo,
                  teste_identificacao_monotonica,
                  teste_requisitos_argissolos_e_luvissolos_6ed,
                  teste_contencao, teste_contencao_5ed,
                  teste_explicador, teste_contencao_por_ablacao,
                  teste_b_sem_sufixo_legivel, teste_prefixo_romano,
                  teste_niveis_2_e_3, teste_textura_arenosa_pela_norma,
                  teste_simbolo_antigo_com_mais_de_uma_leitura,
                  teste_soma_ca_mg_do_acervo, teste_a_chernozemico_por_kleene,
                  teste_espessura_do_a_chernozemico, teste_v_do_boletim,
                  teste_concrecionario_nos_neossolos_5ed,
                  teste_mosqueado_incompleto_nao_veta_plintico,
                  teste_organico_acima_da_superficie,
                  teste_espessura_do_b_latossolico,
                  teste_b_nitico_por_kleene,
                  teste_cotejo_causas_da_nao_conclusao,
                  teste_tipicidade_fisicamente_possivel,
                  teste_registro_de_curadoria_classificado,
                  teste_glei_em_solo_arenoso_nos_neossolos_5ed):
        teste()
    print(f"\n{'FALHAS: ' + str(len(_falhas)) if _falhas else 'tudo passou'}")
    return 1 if _falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
