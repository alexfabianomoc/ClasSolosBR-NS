#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adaptador BDSolos -> contrato da API SmartSolosExpert.

Converte o CSV do BDSolos (Embrapa/Redape, 275 colunas, uma linha por
horizonte) para o formato ProfileList aceito pelo recurso /verification da
AgroAPI. Somente biblioteca padrao do Python 3.

    python tools/bdsolos_adapter.py --relatorio
    python tools/bdsolos_adapter.py --nivel-minimo 4 --saida bdsolos_l4.json
    python tools/agroapi_verify.py --arquivo bdsolos_l4.json

CHAVE DO PERFIL
    O CSV nao tem coluna de identificador de perfil. A chave e a tripla
    (Codigo Trabalho, Codigo PA, Numero PA), que produz exatamente os 8.925
    perfis declarados nos metadados do dataset -- nenhuma das colunas isoladas
    produz esse numero (Codigo PA sozinho da 8.175).

ROTULO DE REFERENCIA
    Vem das colunas ja decompostas do CSV, nao do texto livre de
    "Classificacao Atual":
        ORDEM     <- Classe de Solos Nivel 1
        SUBORDEM  <- Classe de Solos Nivel 2, menos o prefixo do nivel 1
        GDE_GRUPO <- Classe de Solos Nivel 3, menos o prefixo do nivel 2
        SUBGRUPO  <- 1a/2a/3a Ocorrencia
    A completude cai rapido com a profundidade taxonomica -- ver --relatorio.
    Use --nivel-minimo para selecionar so os perfis utilizaveis na medida que
    voce pretende reportar.

O QUE ESTE ADAPTADOR NAO RESOLVE
    Sete campos booleanos do contrato (RETRATIL, SOMBRICO, REDOXICO,
    MATERIAIS_PRIMARIOS, ATIVIDADES_HUMANAS, PLACICO_TOPO, MANGANES) nao tem
    coluna correspondente no CSV, ou so existem em nivel de perfil quando o
    contrato os pede por horizonte. Sao omitidos, e a omissao e informacao:
    o motor simbolico vai decidir sem eles. Ver a secao de premissas em
    wiki/outputs/adaptador-bdsolos-para-api.md antes de citar qualquer numero.
"""

import argparse
import collections
import csv
import io
import json
import os
import sys
import unicodedata

csv.field_size_limit(10 ** 7)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PADRAO = os.path.join(RAIZ, "raw", "bd_solos_para_redape.csv")

# Indices de coluna do CSV do BDSolos (275 colunas, separador ";").
COL = {
    "trabalho": 0, "cod_pa": 8, "num_pa": 9, "num_campo": 10,
    "uf": 21, "municipio": 22,
    "class_original": 50, "class_atual": 51,
    "nivel3": 54, "oc1": 55, "oc2": 56, "oc3": 57, "oc4": 58,
    "nivel2": 59, "nivel1": 60,
    "drenagem": 85,
    "simb_horiz": 104, "prof_sup": 105, "prof_inf": 106,
    "umida_matiz": 110, "umida_valor": 111, "umida_croma": 112,
    "amassada_matiz": 114, "amassada_valor": 115, "amassada_croma": 116,
    "seca_matiz": 118, "seca_valor": 119, "seca_croma": 120,
    "seca_trit_matiz": 122, "seca_trit_valor": 123, "seca_trit_croma": 124,
    "estrutura_grau": 125, "estrutura_tamanho": 128, "estrutura_forma": 131,
    "consistencia_seca": 134,
    "cerosidade_grau": 138, "cerosidade_quant": 139,
    "transicao_topografia": 157, "transicao_nitidez": 158,
    "mosq_matiz": 167, "mosq_valor": 168, "mosq_croma": 169,
    "calhaus": 170, "cascalho": 171,
    "areia_grossa": 173, "areia_fina": 174, "silte": 176, "argila": 177,
    "ph_agua": 208, "ph_kcl": 209,
    "ca": 211, "mg": 212, "ca_mg": 213, "k": 214, "na": 215, "h": 217, "al": 218,
    "v_boletim": 220,
    "fe2o3": 224,
    "p_assim": 231, "c_org": 232,
    "cond_eletr": 237, "equi_caco3": 249,
}

# ----------------------------------------------------------------------------
# Vocabularios: texto do BDSolos -> codigo inteiro do contrato da API.
# As escalas vem das descricoes do proprio Swagger; ver
# wiki/sources/agroapi-smartsolos-expert-v1-swagger.md.
# ----------------------------------------------------------------------------

# "de excessivamente drenado (1) a muito mal drenado (8)"
DRENAGEM = {
    "excessivamente drenado": 1,
    "fortemente drenado": 2,
    "acentuadamente drenado": 3,
    "bem drenado": 4,
    "moderadamente drenado": 5,
    "imperfeitamente drenado": 6,
    "mal drenado": 7,
    "muito mal drenado": 8,
}

# "de ausente (1) a forte (4)"
ESTRUTURA_GRAU = {"ausente": 1, "fraca": 2, "moderada": 3, "forte": 4}

# "de muito pequeno (1) a extremamente grande (6)"
ESTRUTURA_TAMANHO = {
    "ultrapequena": 1,   # abaixo de "muito pequena"; a escala da API nao preve
    "muito pequena": 1,
    "pequena": 2,
    "media": 3,
    "grande": 4,
    "muito grande": 5,
    "extremamente grande": 6,
}

# laminar (1) ... grumosa (7). "Macica", "Graos simples" e afins sao AUSENCIA
# de estrutura e nao tem codigo no contrato: o campo e omitido.
ESTRUTURA_TIPO = {
    "laminar": 1,
    "prismatica": 2,
    "colunar": 3,
    "blocos angulares": 4,
    "blocos subangulares": 5,
    "granular": 6,
    "grumosa": 7,
}

# Formas que afirmam AUSENCIA de estrutura: viram ESTRUTURA_GRAU = 1 (ausente),
# sem ESTRUTURA_TIPO. Ficam de fora "... que se desfaz" (estrutura secundaria)
# e "estrutura composta" (dois tipos), que nao sao ausencia.
FORMAS_AUSENCIA = {
    "macica", "graos simples", "macica porosa",
    "macica nao coerente", "macica porosa nao coerente",
}

CEROSIDADE_GRAU = {"ausente": 1, "fraca": 2, "moderada": 3, "forte": 4}
CEROSIDADE_QUANT = {"pouca": 1, "comum": 2, "abundante": 3}

# "de abrupta (1) a difusa (4)"
TRANSICAO_GRAU = {"abrupta": 1, "clara": 2, "gradual": 3, "difusa": 4}

# plana (1), ondulada (2), irregular (3), descontinua (4)
TRANSICAO_FORMA = {"plana": 1, "ondulada": 2, "irregular": 3,
                   "descontinua": 4, "quebrada": 4}

# "de solto (1) a extremamente duro (6)"
CONSISTENCIA_SECO = {
    "solta": 1, "macia": 2, "ligeiramente dura": 3,
    "dura": 4, "muito dura": 5, "extremamente dura": 6,
}

# Faixas de sanidade: descartam valor fora do fisicamente possivel em vez de
# enviar lixo ao motor de regras. O CSV tem pH 601 e argila 1000, entre outros.
FAIXAS = {
    "LIMITE_SUP": (0, 1000), "LIMITE_INF": (0, 1000),
    "COR_UMIDA_VALOR": (0, 10), "COR_UMIDA_CROMA": (0, 10),
    "COR_SECA_VALOR": (0, 10), "COR_SECA_CROMA": (0, 10),
    "COR_UMIDA_AMASSADA_VALOR": (0, 10), "COR_UMIDA_AMASSADA_CROMA": (0, 10),
    "COR_SECA_TRITURADA_VALOR": (0, 10), "COR_SECA_TRITURADA_CROMA": (0, 10),
    "COR_MOSQ_VALOR_1": (0, 10), "COR_MOSQ_CROMA_1": (0, 10),
    "CALHAU": (0, 1000), "CASCALHO": (0, 1000),
    "AREIA_GROS": (0, 1000), "AREIA_FINA": (0, 1000),
    "SILTE": (0, 1000), "ARGILA": (0, 1000),
    "PH_AGUA": (0, 14), "PH_KCL": (0, 14),
    "C_ORG": (0, 600), "P_ASSIM": (0, 2000),
    "CA_TROC": (0, 100), "MG_TROC": (0, 100), "CA_MG_TROC": (0, 200), "K_TROC": (0, 100),
    "V_BOLETIM": (0, 100),
    "NA_TROC": (0, 100), "AL_TROC": (0, 100), "H_TROC": (0, 100),
    "COND_ELETR": (0, 200), "EQUI_CACO3": (0, 1000), "TEOR_FE": (0, 1000),
}


# --------------------------------------------------------------- normalizacao

def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn")


def chave(texto):
    """Minusculas, sem acento, espacos colapsados -- para bater no vocabulario."""
    return " ".join(sem_acento(texto or "").lower().split())


def primeiro_termo(texto):
    """'Fraca a moderada' -> 'fraca'. 'Pequena a media' -> 'pequena'.

    Decisao de projeto: valor composto vira o termo MENOS desenvolvido. E a
    leitura conservadora -- nao inventa um grau que o descritor nao afirmou.
    Registrada no relatorio para poder ser auditada.
    """
    k = chave(texto)
    for separador in (" a ", "/", " ate ", " - "):
        if separador in k:
            k = k.split(separador)[0].strip()
            break
    return k


def normalizar_drenagem(texto):
    """'Imperfeitamente a moderadamente drenado' -> 'imperfeitamente drenado'.

    O CSV escreve a faixa omitindo o substantivo no primeiro termo. Sem esta
    normalizacao, 461 perfis perderiam a DRENAGEM -- o unico atributo de perfil
    que o contrato aceita, e que o PYKKA7 nao traz em nenhum registro.
    """
    k = chave(texto)
    if not k:
        return k
    if " a " in k:
        k = k.split(" a ")[0].strip()
    if k and not k.endswith("drenado"):
        k += " drenado"
    return k


def codificar(texto, vocabulario, contador=None, rotulo=""):
    """Texto -> codigo inteiro. Registra o que nao casou, em vez de silenciar."""
    if not (texto or "").strip():
        return None
    k = primeiro_termo(texto)
    if k in vocabulario:
        return vocabulario[k]
    # Tentativa por prefixo: 'blocos subangulares que se desfaz' -> blocos subangulares
    for termo, codigo in vocabulario.items():
        if k.startswith(termo):
            return codigo
    if contador is not None:
        contador["%s :: %s" % (rotulo, texto.strip()[:50])] += 1
    return None


def numero(texto, campo=None):
    """Converte para numero, aplicando a faixa de sanidade do campo."""
    s = (texto or "").strip().replace(",", ".")
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if campo in FAIXAS:
        minimo, maximo = FAIXAS[campo]
        if not (minimo <= v <= maximo):
            return None
    return int(v) if v == int(v) else v


def matiz(texto):
    """'7,5YR' -> '7.5YR'. Mosqueado empacotado ('10YR:5YR') -> primeira cor."""
    s = (texto or "").strip()
    if not s:
        return None
    s = s.split(":")[0].strip().replace(",", ".")
    return s or None


def valor_empacotado(texto, campo):
    """'5:6' -> 5. Mesma logica do matiz, para valor e croma do mosqueado."""
    s = (texto or "").strip().split(":")[0]
    return numero(s, campo)


# ------------------------------------------------------------------- conversao

def _subtrair_prefixo(completo, prefixo):
    """'ARGISSOLO VERMELHO-AMARELO' menos 'ARGISSOLO' -> 'VERMELHO-AMARELO'."""
    c, p = (completo or "").strip(), (prefixo or "").strip()
    if not c:
        return None
    if p and c.upper().startswith(p.upper()):
        resto = c[len(p):].strip()
        return resto or None
    return c or None


def texto_corrobora_rotulo(ordem, class_atual):
    """A ordem das colunas decompostas aparece no texto da Classificacao Atual?

    O BDSolos guarda a classe em dois lugares: o texto livre de "Classificacao
    Atual" e as colunas ja decompostas por nivel, que sao a fonte do rotulo
    deste adaptador. Os dois nem sempre coincidem:

    * quando o texto registra reclassificacao, as colunas o acompanham em
      97,4% dos perfis -- sao a decomposicao dele;
    * quando o texto nao mudou, divergem em cerca de metade. Na maioria o
      texto ficou em nomenclatura anterior ao SiBCS (Podzolico, Latossol) e a
      coluna traz a correlacao moderna -- a coluna esta certa;
    * em 26 perfis as duas formas trazem nomes VIGENTES que se contradizem na
      ordem (ex.: texto "GLEISSOLO HAPLICO Ta Aluminico cambico", coluna
      "CAMBISSOLO"). Esses sao erro do acervo.

    Criterio adotado em 2026-10-13: so entra na avaliacao o perfil cujo rotulo
    de coluna o texto confirma. Exclui os 26 contraditorios e tambem aqueles
    cuja reclassificacao existe so na coluna, por procedimento que o produtor
    nao documenta. E conservador de proposito.
    """
    o = chave(ordem).upper()
    t = chave(class_atual).upper()
    if not o or not t:
        return False
    palavras = t.replace("-", " ").replace(",", " ").split()
    return bool(palavras) and (palavras[0] == o or o in palavras[:4])


def rotulo_de_referencia(linha):
    """Monta os quatro niveis a partir das colunas decompostas do CSV."""
    n1 = (linha[COL["nivel1"]] or "").strip()
    n2 = (linha[COL["nivel2"]] or "").strip()
    n3 = (linha[COL["nivel3"]] or "").strip()
    ocorrencias = [(linha[COL[c]] or "").strip()
                   for c in ("oc1", "oc2", "oc3", "oc4")]
    ocorrencias = [o for o in ocorrencias if o]

    rotulo = {}
    if n1:
        rotulo["ORDEM"] = n1.upper()
    subordem = _subtrair_prefixo(n2, n1)
    if subordem:
        rotulo["SUBORDEM"] = subordem.upper()
    grande_grupo = _subtrair_prefixo(n3, n2)
    if grande_grupo:
        rotulo["GDE_GRUPO"] = grande_grupo
    if ocorrencias:
        # O contrato usa subgrupo em minusculas ("tipico", "abruptico").
        rotulo["SUBGRUPO"] = " ".join(o.lower() for o in ocorrencias)
    return rotulo


def nivel_do_rotulo(rotulo):
    """Ate que nivel categorico este perfil tem rotulo (0 a 4)."""
    for i, campo in enumerate(("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")):
        if not rotulo.get(campo):
            return i
    return 4


def converter_horizonte(linha, nao_mapeados):
    h = {}

    def por(campo, coluna, conversor=numero):
        v = conversor(linha[COL[coluna]], campo) if conversor is numero \
            else conversor(linha[COL[coluna]])
        if v is not None:
            h[campo] = v

    simbolo = (linha[COL["simb_horiz"]] or "").strip()
    if simbolo:
        h["SIMB_HORIZ"] = simbolo
    por("LIMITE_SUP", "prof_sup")
    por("LIMITE_INF", "prof_inf")

    for prefixo, colunas in (
        ("COR_UMIDA", ("umida_matiz", "umida_valor", "umida_croma")),
        ("COR_SECA", ("seca_matiz", "seca_valor", "seca_croma")),
        ("COR_UMIDA_AMASSADA", ("amassada_matiz", "amassada_valor", "amassada_croma")),
        ("COR_SECA_TRITURADA", ("seca_trit_matiz", "seca_trit_valor", "seca_trit_croma")),
    ):
        m = matiz(linha[COL[colunas[0]]])
        if m:
            h[prefixo + "_MATIZ"] = m
        for sufixo, coluna in (("_VALOR", colunas[1]), ("_CROMA", colunas[2])):
            v = numero(linha[COL[coluna]], prefixo + sufixo)
            if v is not None:
                h[prefixo + sufixo] = v

    m = matiz(linha[COL["mosq_matiz"]])
    if m:
        h["COR_MOSQ_MATIZ_1"] = m
    for campo, coluna in (("COR_MOSQ_VALOR_1", "mosq_valor"),
                          ("COR_MOSQ_CROMA_1", "mosq_croma")):
        v = valor_empacotado(linha[COL[coluna]], campo)
        if v is not None:
            h[campo] = v

    for campo, coluna, vocabulario in (
        ("ESTRUTURA_GRAU", "estrutura_grau", ESTRUTURA_GRAU),
        ("ESTRUTURA_TAMANHO", "estrutura_tamanho", ESTRUTURA_TAMANHO),
        ("ESTRUTURA_TIPO", "estrutura_forma", ESTRUTURA_TIPO),
        ("CEROSIDADE_GRAU", "cerosidade_grau", CEROSIDADE_GRAU),
        ("CEROSIDADE_QUANTIDADE", "cerosidade_quant", CEROSIDADE_QUANT),
        ("TRANSICAO_GRAU", "transicao_nitidez", TRANSICAO_GRAU),
        ("TRANSICAO_FORMA", "transicao_topografia", TRANSICAO_FORMA),
        ("CONSISTENCIA_SECO", "consistencia_seca", CONSISTENCIA_SECO),
    ):
        v = codificar(linha[COL[coluna]], vocabulario, nao_mapeados, campo)
        if v is not None:
            h[campo] = v

    # Ausencia de estrutura (2026-10-12). O contrato nao tem TIPO para "macica"
    # ou "graos simples", mas tem GRAU "ausente (1)". Sem isto, o horizonte
    # chegava sem nenhuma informacao de estrutura, como se nada tivesse sido
    # descrito. So vale para a ausencia pura e com grau vazio na fonte; as formas
    # "... que se desfaz" descrevem estrutura secundaria e continuam sem codigo.
    if "ESTRUTURA_GRAU" not in h and not (linha[COL["estrutura_grau"]] or "").strip():
        forma = chave(linha[COL["estrutura_forma"]])
        if forma in FORMAS_AUSENCIA:
            h["ESTRUTURA_GRAU"] = ESTRUTURA_GRAU["ausente"]

    for campo, coluna in (
        ("CALHAU", "calhaus"), ("CASCALHO", "cascalho"),
        ("AREIA_GROS", "areia_grossa"), ("AREIA_FINA", "areia_fina"),
        ("SILTE", "silte"), ("ARGILA", "argila"),
        ("PH_AGUA", "ph_agua"), ("PH_KCL", "ph_kcl"),
        ("CA_TROC", "ca"), ("MG_TROC", "mg"), ("K_TROC", "k"),
        ("NA_TROC", "na"), ("H_TROC", "h"), ("AL_TROC", "al"),
        ("P_ASSIM", "p_assim"), ("C_ORG", "c_org"),
        ("COND_ELETR", "cond_eletr"), ("EQUI_CACO3", "equi_caco3"),
        # Teor de ferro: Fe2O3 do ataque sulfurico (70,6% preenchido, mediana
        # 43,7 g/kg) e nao CDB-Ferro (2,0% preenchido) -- as magnitudes batem
        # com o TEOR_FE do PYKKA7 (mediana 37,0).
        ("TEOR_FE", "fe2o3"),
    ):
        por(campo, coluna)

    # Soma Ca + Mg (2026-10-16, decisao do usuario). Em 37,4% dos horizontes do
    # BDSolos com dado de Ca/Mg, o laudo traz so a soma ("Complexo Sortivo -
    # Ca + Mg"), e o contrato da API pede Ca e Mg separados: sem este campo, o
    # nucleo recebia Ca e Mg vazios e nao calculava S, T, V% nem a atividade
    # da argila, que so dependem da soma. Vai FORA do contrato, com prefixo
    # "_" (agroapi_verify.limpar o descarta antes do envio), e nunca e
    # repartido entre Ca e Mg -- isso seria inventar dado.
    v = numero(linha[COL["ca_mg"]], "CA_MG_TROC")
    if v is not None:
        h["_CA_MG_TROC"] = v

    # V do boletim (2026-10-17, decisao do usuario, opcao c). O contrato da
    # API nao tem campo de V: o SmartSolos, como o nucleo, o calcula de S/T.
    # O laudo do BDSolos traz o V informado ("Complexo Sortivo - Valor V"),
    # que o nucleo usa quando faltam componentes e como arbitro quando o
    # calculo e o informado caem em lados opostos de um limiar. Vai FORA do
    # contrato, com prefixo "_", como a soma Ca + Mg.
    v = numero(linha[COL["v_boletim"]], "V_BOLETIM")
    if v is not None:
        h["_V_BOLETIM"] = v

    return h


def ler_perfis(caminho=CSV_PADRAO, com_procedencia=False):
    """Le o CSV inteiro e devolve (perfis, estatisticas).

    Uma passada, agrupando por (Codigo Trabalho, Codigo PA, Numero PA).
    Os horizontes saem na ordem em que aparecem no arquivo.
    """
    if not os.path.isfile(caminho):
        raise SystemExit("CSV do BDSolos nao encontrado em %s" % caminho)

    perfis = collections.OrderedDict()
    nao_mapeados = collections.Counter()
    simbolos_brutos = collections.Counter()
    linhas = descartadas = 0
    chaves_truncadas = set()

    with io.open(caminho, encoding="utf-8", newline="") as fp:
        leitor = csv.reader(fp, delimiter=";")
        next(leitor)
        for linha in leitor:
            linhas += 1
            # Registro corrompido na origem (2026-10-14): em tres horizontes
            # do perfil 797|12743|RS-142, aspas internas sem escape
            # ('"Arenitos da formacao "Camaqua".') partem o registro em dois.
            # A 1a metade sai truncada (16 colunas); a 2a (258) tem as colunas
            # deslocadas e um 'Codigo Trabalho' que nao e codigo. Sem este
            # filtro, as metades formavam um perfil inexistente, aceito como
            # utilizavel, com valores fora de lugar (pH 1,2; cor 'Solta').
            if len(linha) <= COL["prof_inf"]:
                descartadas += 1
                chaves_truncadas.add(tuple(c.strip() for c in (
                    linha[COL["trabalho"]], linha[COL["cod_pa"]],
                    linha[COL["num_pa"]])))
                continue
            if not linha[COL["trabalho"]].strip().isdigit():
                descartadas += 1
                continue
            ident = (linha[COL["trabalho"]].strip(),
                     linha[COL["cod_pa"]].strip(),
                     linha[COL["num_pa"]].strip())
            perfil = perfis.get(ident)
            if perfil is None:
                perfil = {"ID_PONTO": "BDSolos|%s|%s|%s" % ident}
                perfil.update(rotulo_de_referencia(linha))
                perfil["HORIZONTES"] = []
                drenagem = codificar(normalizar_drenagem(linha[COL["drenagem"]]),
                                     DRENAGEM, nao_mapeados, "DRENAGEM")
                if drenagem is not None:
                    perfil["DRENAGEM"] = drenagem
                perfil["_corroborado"] = texto_corrobora_rotulo(
                    perfil.get("ORDEM"), linha[COL["class_atual"]])
                if com_procedencia:
                    perfil["_uf"] = linha[COL["uf"]].strip()
                    perfil["_municipio"] = linha[COL["municipio"]].strip()
                    perfil["_class_original"] = linha[COL["class_original"]].strip()
                    perfil["_class_atual"] = linha[COL["class_atual"]].strip()
                perfis[ident] = perfil
            bruto = linha[COL["simb_horiz"]] or ""
            if bruto.strip():
                simbolos_brutos[bruto] += 1
            horizonte = converter_horizonte(linha, nao_mapeados)
            if horizonte:
                perfil["HORIZONTES"].append(horizonte)

    estatisticas = {
        "linhas_lidas": linhas,
        "linhas_descartadas": descartadas,
        "perfis_corrompidos": len(chaves_truncadas - set(perfis)),
        "perfis": len(perfis),
        "sem_horizonte": sum(1 for p in perfis.values() if not p["HORIZONTES"]),
        "nao_mapeados": nao_mapeados,
        "simbolos": contar_simbolos(simbolos_brutos, perfis.values()),
    }
    return list(perfis.values()), estatisticas


def contar_simbolos(brutos, perfis):
    """Verificacao da mitigacao 10 (monografia, secao 3.5).

    O simbolo do horizonte decide a classe: a caixa distingue horizonte
    principal (maiuscula) de sufixo (minuscula) -- 'AB' e transicao, 'Ab'
    e A enterrado; 'Bt' e B textural. A unica transformacao admitida e a
    remocao de espacos circundantes ('A ' -> 'A'). Conta os simbolos em
    tres pontos -- grafia bruta, apos a remocao de espacos, apos a
    conversao -- e os grupos que uma uniformizacao de caixa fundiria.
    """
    aparados = collections.Counter()
    for s, q in brutos.items():
        aparados[s.strip()] += q
    convertidos = collections.Counter(
        h["SIMB_HORIZ"] for p in perfis for h in p["HORIZONTES"]
        if "SIMB_HORIZ" in h)
    por_caixa = collections.defaultdict(set)
    for s in aparados:
        por_caixa[s.upper()].add(s)
    return {
        "brutos": brutos,
        "aparados": aparados,
        "convertidos": convertidos,
        "grupos_espaco": sum(1 for s in aparados
                             if sum(1 for b in brutos if b.strip() == s) > 1),
        "grupos_caixa": sorted(g for g in por_caixa.values() if len(g) > 1),
    }


# ------------------------------------------------------------------- selecao

SOBREPOSICAO_PYKKA7 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "dados", "sobreposicao_pykka7_bdsolos.json")


def ids_do_conjunto_curado():
    """Registros do BDSolos que repetem perfis do PYKKA7 (2026-10-14).

    36 dos 94 perfis curados estao tambem no BDSolos (40 registros): mesmos
    limites e mesma argila, em notacao anterior. Ficam fora dos conjuntos de
    avaliacao -- as regras foram depuradas no PYKKA7, e a verificacao fora da
    amostra nao pode conte-los (monografia, secoes 3.2 e 3.5).
    """
    if not os.path.isfile(SOBREPOSICAO_PYKKA7):
        raise SystemExit("lista de sobreposicao nao encontrada: %s" % SOBREPOSICAO_PYKKA7)
    with io.open(SOBREPOSICAO_PYKKA7, encoding="utf-8") as fp:
        pares = json.load(fp)["pares"]
    return {i for ids in pares.values() for i in ids}


def filtrar(perfis, nivel_minimo=0, ordem=None, minimo_horizontes=1,
            corroborado=False, sem_curado=False):
    excluidos = ids_do_conjunto_curado() if sem_curado else set()
    saida = []
    for p in perfis:
        if len(p.get("HORIZONTES") or []) < minimo_horizontes:
            continue
        if corroborado and not p.get("_corroborado"):
            continue
        if p.get("ID_PONTO") in excluidos:
            continue
        if nivel_minimo and nivel_do_rotulo(p) < nivel_minimo:
            continue
        if ordem and (p.get("ORDEM") or "").upper() != ordem.upper():
            continue
        saida.append(p)
    return saida


def estratificar(perfis, por_ordem):
    """Amostra ate N perfis de cada ordem -- conjunto balanceado como o PYKKA7."""
    baldes = collections.OrderedDict()
    for p in perfis:
        baldes.setdefault(p.get("ORDEM") or "(sem ordem)", []).append(p)
    saida = []
    for ordem in sorted(baldes):
        saida.extend(baldes[ordem][:por_ordem])
    return saida


# ------------------------------------------------------------------ relatorio

def relatar(perfis, estatisticas, detalhado=False):
    total = len(perfis)
    horizontes = sum(len(p.get("HORIZONTES") or []) for p in perfis)
    niveis = collections.Counter(nivel_do_rotulo(p) for p in perfis)
    ordens = collections.Counter(p.get("ORDEM") or "(sem ordem)" for p in perfis)
    com_drenagem = sum(1 for p in perfis if "DRENAGEM" in p)

    print("=" * 70)
    print("CONVERSAO BDSolos -> contrato SmartSolosExpert")
    print("=" * 70)
    print("linhas lidas (horizontes) ... %d" % estatisticas["linhas_lidas"])
    print("linhas descartadas .......... %d (registros corrompidos na origem: aspas"
          % estatisticas["linhas_descartadas"])
    print("                               sem escape partem o registro em dois)")
    print("perfis no CSV ............... %d (+ %d descartado por registro corrompido)"
          % (estatisticas["perfis"], estatisticas.get("perfis_corrompidos", 0)))
    if estatisticas.get("sem_horizonte"):
        print("  sem nenhum horizonte ...... %d (registro so de perfil -- a API precisa"
              % estatisticas["sem_horizonte"])
        print("                               dos horizontes como evidencia)")
    print("perfis utilizaveis .......... %d" % total)
    print("horizontes convertidos ...... %d (media %.2f por perfil)"
          % (horizontes, horizontes / float(total or 1)))
    print("perfis com DRENAGEM ......... %d (%.1f%%)"
          % (com_drenagem, 100.0 * com_drenagem / (total or 1)))
    print()
    print("COMPLETUDE DO ROTULO DE REFERENCIA")
    print("-" * 70)
    print("  Ate que nivel o BDSolos rotula o perfil -- e portanto ate onde a")
    print("  metrica L0-L4 pode ser lida sem viés de rotulo ausente.")
    print()
    acumulado = 0
    for nivel in (4, 3, 2, 1):
        acumulado += niveis.get(nivel, 0)
        nome = {1: "ordem", 2: "+ subordem", 3: "+ grande grupo",
                4: "+ subgrupo (completo)"}[nivel]
        print("    rotulo ate nivel %d (%-22s) %5d perfis  (%.1f%%)"
              % (nivel, nome, acumulado, 100.0 * acumulado / (total or 1)))
    print("    sem rotulo de ordem                      %5d perfis"
          % niveis.get(0, 0))
    print()
    print("DISTRIBUICAO POR ORDEM")
    print("-" * 70)
    for ordem, q in ordens.most_common():
        print("    %-26s %5d" % (ordem, q))

    campos = collections.Counter()
    for p in perfis:
        for h in p.get("HORIZONTES") or []:
            campos.update(h.keys())
    print()
    print("PREENCHIMENTO DOS CAMPOS DE HORIZONTE (de %d horizontes)" % horizontes)
    print("-" * 70)
    for campo, q in campos.most_common():
        print("    %5.1f%%  %s" % (100.0 * q / (horizontes or 1), campo))

    ausentes = ["RETRATIL", "SOMBRICO", "REDOXICO", "MATERIAIS_PRIMARIOS",
                "ATIVIDADES_HUMANAS", "PLACICO_TOPO", "MANGANES",
                "LAMELA_SUP", "LAMELA_INF", "LAMELA_TEXTURA"]
    print()
    print("CAMPOS DO CONTRATO SEM ORIGEM NO CSV (sempre omitidos)")
    print("-" * 70)
    print("    " + ", ".join(ausentes))
    print("    Os sete primeiros sao caracteres diagnosticos que o contrato pede")
    print("    por horizonte e o CSV so registra por perfil, quando registra.")

    simb = estatisticas.get("simbolos")
    if simb:
        perdidos = set(simb["aparados"]) - set(simb["convertidos"])
        print()
        print("PRESERVACAO DO SIMBOLO DO HORIZONTE (mitigacao 10, todo o CSV)")
        print("-" * 70)
        print("    grafias brutas distintas ......... %5d em %d horizontes"
              % (len(simb["brutos"]), sum(simb["brutos"].values())))
        print("    apos remover espacos circundantes  %5d (%d grupos fundidos,"
              % (len(simb["aparados"]), simb["grupos_espaco"]))
        print("                                              ex.: 'A ' -> 'A')")
        print("    apos a conversao ................. %5d em %d horizontes"
              % (len(simb["convertidos"]), sum(simb["convertidos"].values())))
        print("    simbolos perdidos na conversao ... %5d%s"
              % (len(perdidos), "" if not perdidos else "  <-- DEFEITO: "
                 + ", ".join(sorted(perdidos)[:10])))
        print("    grupos que a uniformizacao de caixa fundiria: %d (nao aplicada)"
              % len(simb["grupos_caixa"]))
        for exemplo in ("AB", "BT"):
            grupo = [g for g in simb["grupos_caixa"]
                     if any(s.upper() == exemplo for s in g)]
            if grupo:
                print("      ex.: " + "  ".join("%s=%d" % (s, simb["aparados"][s])
                                               for s in sorted(grupo[0])))

    nao_mapeados = estatisticas["nao_mapeados"]
    if nao_mapeados:
        print()
        print("VALORES DE TEXTO SEM CODIGO NO CONTRATO (%d distintos)"
              % len(nao_mapeados))
        print("-" * 70)
        limite = None if detalhado else 25
        for termo, q in nao_mapeados.most_common(limite):
            print("    %6d  %s" % (q, termo))
        if limite and len(nao_mapeados) > limite:
            print("    ... e mais %d (use --detalhado)." % (len(nao_mapeados) - limite))
        print()
        print("    'ESTRUTURA_TIPO :: Maciça' e afins nao sao defeito: sao")
        print("    ausencia de estrutura, sem TIPO no contrato. Desde 2026-10-12")
        print("    a ausencia pura (com grau vazio na fonte) vai como")
        print("    ESTRUTURA_GRAU = 1 (ausente); '... que se desfaz' continua sem codigo.")


# ------------------------------------------------------------------------ cli

def principal(argv=None):
    p = argparse.ArgumentParser(
        description="Converte o CSV do BDSolos para o formato de entrada da "
                    "API SmartSolosExpert.",
        epilog="A saida alimenta: python tools/agroapi_verify.py --arquivo <saida>",
    )
    p.add_argument("--csv", default=CSV_PADRAO, help="caminho do CSV do BDSolos")
    p.add_argument("--saida", help="grava o ProfileList JSON neste caminho")
    p.add_argument("--nivel-minimo", type=int, choices=(1, 2, 3, 4), default=0,
                   help="so perfis com rotulo completo ate este nivel categorico")
    p.add_argument("--ordem", help="filtra por uma ordem (ex.: LATOSSOLO)")
    p.add_argument("--corroborado", action="store_true",
                   help="so perfis cuja ordem das colunas o texto da "
                        "Classificacao Atual confirma (criterio da monografia)")
    p.add_argument("--sem-curado", action="store_true",
                   help="exclui os registros que repetem perfis do PYKKA7 "
                        "(criterio da monografia, junto com --corroborado)")
    p.add_argument("--minimo-horizontes", type=int, default=1,
                   help="descarta perfis com menos horizontes que isto")
    p.add_argument("--estratificar", type=int, metavar="N",
                   help="amostra ate N perfis por ordem (conjunto balanceado)")
    p.add_argument("--limite", type=int, help="usa apenas os N primeiros perfis")
    p.add_argument("--procedencia", action="store_true",
                   help="mantem UF, municipio e os textos de classificacao "
                        "(campos _prefixados, removidos antes do envio)")
    p.add_argument("--relatorio", action="store_true",
                   help="imprime o relatorio de conversao")
    p.add_argument("--detalhado", action="store_true",
                   help="no relatorio, lista todos os valores nao mapeados")
    args = p.parse_args(argv)

    perfis, estatisticas = ler_perfis(args.csv, com_procedencia=args.procedencia)
    perfis = filtrar(perfis, args.nivel_minimo, args.ordem,
                     args.minimo_horizontes, args.corroborado, args.sem_curado)
    if args.estratificar:
        perfis = estratificar(perfis, args.estratificar)
    if args.limite:
        perfis = perfis[:args.limite]

    if args.relatorio or not args.saida:
        relatar(perfis, estatisticas, args.detalhado)

    if args.saida:
        with io.open(args.saida, "w", encoding="utf-8") as fp:
            json.dump({"items": perfis}, fp, ensure_ascii=False, indent=1)
        tamanho = os.path.getsize(args.saida) / 1024.0 / 1024.0
        print()
        print("%d perfis gravados em %s (%.1f MB)" % (len(perfis), args.saida, tamanho))
        print("Proximo passo: python tools/agroapi_verify.py --arquivo %s" % args.saida)
    elif not args.relatorio:
        print()
        print("Nada gravado. Use --saida para produzir o JSON.")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
