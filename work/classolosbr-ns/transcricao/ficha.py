"""Transcrição de uma ficha de perfil (RTF do conjunto curado) para o contrato.

A ficha segue o formato normalizado de descrição de perfil (IBGE, 2015, item
1.1.9.1): descrição morfológica horizonte a horizonte, seguida de quatro
tabelas analíticas — granulometria; pH e complexo sortivo; carbono e ataque
sulfúrico; sódio e sais. Daqui sai, por horizonte:

* símbolo e limites (linha morfológica "Ap 0-15 cm: …");
* cor úmida e seca da matriz e a do primeiro mosqueado (Munsell);
* granulometria, pH, complexo sortivo, P assimilável, C orgânico, Fe₂O₃ e
  P₂O₅ do ataque sulfúrico, equivalente de CaCO₃ e condutividade elétrica.

O que **não** sai daqui: estrutura, cerosidade, transição, consistência e os
caracteres booleanos (COESO, FLUVICO…). Esses vêm do JSON atualizado, casados
pelo horizonte (ver `originais.py`), e a procedência fica registrada.

Decisões de leitura, declaradas:

* "-" e célula vazia → ausente (None), nunca zero;
* "<1" → 1, a convenção dos curadores no JSON: o valor é limite de
  detecção, não medida, e a leitura não o distingue de 1;
* número com vírgula decimal (`1,05`) e número truncado (`10,`) são lidos
  como estão. **Erros de digitação da ficha são preservados** — eles são o
  objeto da avaliação do explicador;
* Ca²⁺ e Mg²⁺ numa célula só (a linha tem uma célula a menos e Ca+Mg+K+Na
  fecha com o Valor S): CA_TROC e MG_TROC ficam None, e a soma vai para
  `_CA_MG_SOMADOS`. É assim que a ficha original registra (`PE_004`).
"""

from __future__ import annotations

import re

_LINHA_MORFO = re.compile(
    r"^(?P<simb>\S+)\s+(?P<sup>\d+(?:[.,]\d+)?)(?:\s*-\s*(?P<inf>\d+(?:[.,]\d+)?))?\s*(?P<mais>\+?)\s*cm\s*(?P<mais2>\+?)\s*[:;]",
    re.M)
_MUNSELL = r"\((?P<matiz>\d+(?:[.,]\d+)?\s*[A-Z]{1,2})[\s,]+(?P<valor>\d+(?:[.,]\d+)?)\s*/\s*(?P<croma>\d+(?:[.,]\d+)?)(?P<resto>[^)]*)\)"
_COR = re.compile(_MUNSELL)


def numero(celula: str | None):
    """'1,05' → 1.05; '10,' → 10.0; '-', '' → None; '<1' → 1."""
    if celula is None:
        return None
    c = celula.strip().replace(" ", "")
    if c in ("", "-", "--", "—", "nd", "n.d."):
        return None
    if c.startswith("<"):
        # Limite de detecção. Os curadores gravam "<1" como 1 no JSON;
        # segue-se a convenção, para que ela não apareça como alteração.
        c = c[1:].strip()
    c = c.rstrip(",").replace(",", ".")
    try:
        return float(c)
    except ValueError:
        return None


def _matiz(texto: str) -> str:
    return texto.replace(",", ".").replace(" ", "")


def _cores(trecho: str) -> dict:
    """Cor úmida, seca e do primeiro mosqueado de uma linha morfológica."""
    saida = {}
    # A cor da matriz vem antes de qualquer feição: mosqueado, pontuações,
    # mosqueado de outra origem. "pontuações cinzento-claro (10YR 7/1)" em
    # `RN_014` era lida como cor úmida da matriz (corrigido em 2026-10-15).
    corte = re.search(r"mosqueado|pontua", trecho, re.I)
    matriz = trecho[:corte.start()] if corte else trecho
    for m in _COR.finditer(matriz):
        resto = m.group("resto").lower()
        alvos = []
        if "seca" in resto and "triturada" not in resto:
            alvos.append("COR_SECA")
        if "úmida" in resto or "umida" in resto or not resto.strip(" ,"):
            # "(2,5Y 5/6, úmida e seca)": a mesma cor vale para as duas.
            alvos.append("COR_UMIDA")
        for alvo in alvos:
            if f"{alvo}_VALOR" in saida:
                continue
            saida[f"{alvo}_MATIZ"] = _matiz(m.group("matiz"))
            saida[f"{alvo}_VALOR"] = numero(m.group("valor"))
            saida[f"{alvo}_CROMA"] = numero(m.group("croma"))
    if corte:
        m = _COR.search(trecho[corte.start():])
        if m:
            saida["COR_MOSQ_MATIZ_1"] = _matiz(m.group("matiz"))
            saida["COR_MOSQ_VALOR_1"] = numero(m.group("valor"))
            saida["COR_MOSQ_CROMA_1"] = numero(m.group("croma"))
    return saida


def _morfologia(texto: str):
    horizontes = []
    linhas = texto.split("\n")
    for i, linha in enumerate(linhas):
        m = _LINHA_MORFO.match(linha)
        if not m:
            continue
        trecho = linha
        # Linha quebrada no RTF: junta até a próxima linha de horizonte.
        for seguinte in linhas[i + 1:i + 4]:
            if _LINHA_MORFO.match(seguinte) or not seguinte.strip():
                break
            trecho += " " + seguinte
        sup = numero(m.group("sup"))
        inf = numero(m.group("inf")) if m.group("inf") else None
        aberto = bool(m.group("mais") or m.group("mais2"))
        if inf is not None and sup is not None and inf < sup:
            # "O 7-0 cm": horizonte orgânico **acima** da superfície mineral,
            # medido de 7 cm até 0. Os curadores gravam -7 a 0; a leitura
            # direta (7 a 0) punha o O abaixo do A e rompia a adjacência.
            sup, inf = -sup, inf
        if inf is None and not aberto:
            # "Bi1 1247 cm": o hífen se perdeu na ficha (12-47). Não se
            # adivinha onde: profundidade fica ausente, e o fato é anotado.
            h_aviso = f"{m.group('simb')}: profundidade ilegível ({m.group('sup')} cm)"
            sup = None
        else:
            h_aviso = None
        h = {"SIMB_HORIZ": m.group("simb"), "LIMITE_SUP": sup,
             "LIMITE_INF": inf, "_ABERTO": aberto}
        if h_aviso:
            h["_AVISO_PROFUNDIDADE"] = h_aviso
        h.update(_cores(trecho))
        horizontes.append(h)
    return horizontes


def _tabelas(texto: str) -> dict[str, list[list[str]]]:
    """Separa as quatro tabelas pelo cabeçalho e devolve as linhas de dado."""
    marcas = [("granulometria", "Símbolo\tProf."),
              ("complexo", "\tÁgua\tKCl"),
              ("carbono", "Horizonte\tC Orgânico"),
              ("sodio", "Horizonte\tSat. Na")]
    posicoes = sorted((texto.find(m), nome) for nome, m in marcas if texto.find(m) >= 0)
    saida = {}
    for k, (ini, nome) in enumerate(posicoes):
        fim = posicoes[k + 1][0] if k + 1 < len(posicoes) else len(texto)
        linhas = []
        for linha in texto[ini:fim].split("\n")[1:]:
            celulas = linha.split("\t")
            primeiro = celulas[0].strip()
            if not primeiro or primeiro in ("Horizonte", "Símbolo", "Fe2O3"):
                continue
            while celulas and not celulas[-1].strip():
                celulas.pop()
            if len(celulas) < 2:
                continue
            linhas.append([c.strip() for c in celulas])
        saida[nome] = linhas
    variante = None
    i = texto.find("Símbolo\tProf.")
    if i >= 0 and "Areia 2,0" in texto[i:i + 300]:
        variante = "areia total"
    saida["_variante_granulometria"] = variante
    return saida


def _parear(horizontes, linhas, avisos, tabela):
    """Casa as linhas da tabela com os horizontes.

    Na ordem: símbolo idêntico; símbolo sem distinção de caixa (`AK` × `Ak`
    na mesma ficha); e, para o que sobrar, a ordem — pulando o horizonte R,
    que não tem análise. A ficha original às vezes usa um símbolo na
    morfologia e outro na tabela (`RN_011`: `B1`/`B2` × `B21`/`B22`).
    """
    pares = [None] * len(horizontes)
    livres = list(range(len(linhas)))
    for criterio in (lambda a, b: a == b, lambda a, b: a.lower() == b.lower()):
        for i, h in enumerate(horizontes):
            if pares[i] is not None:
                continue
            for k in livres:
                if criterio(linhas[k][0], h["SIMB_HORIZ"]):
                    pares[i] = linhas[k]
                    livres.remove(k)
                    break
    restantes = [i for i, h in enumerate(horizontes)
                 if pares[i] is None and not h["SIMB_HORIZ"].lstrip("0123456789IV").startswith("R")]
    if livres and len(livres) <= len(restantes):
        avisos.append(f"{tabela}: casadas pela ordem "
                      f"{[(linhas[k][0], horizontes[i]['SIMB_HORIZ']) for k, i in zip(livres, restantes)]}")
        for k, i in zip(livres, restantes):
            pares[i] = linhas[k]
    elif livres:
        avisos.append(f"{tabela}: linhas sem horizonte {[linhas[k][0] for k in livres]}")
    return pares


def _complexo(valores: list[str]):
    """pH, KCl e complexo sortivo, detectando Ca+Mg numa célula só.

    Duas leituras possíveis da linha: a normal (Ca, Mg, K, Na, S, Al, H, T…)
    e a com Ca+Mg somados (uma célula a menos). Escolhe-se a que fecha as
    **duas** somas do próprio laudo — S = bases e T = S + Al + H. Só a soma S
    não basta: em `PE_035` as duas leituras fecham S por coincidência, e só T
    as separa.
    """
    v = [numero(x) for x in valores]
    def fecha(partes, total):
        if total is None or any(p is None for p in partes):
            return False
        return abs(sum(partes) - total) <= 0.051 + 0.02 * abs(total)
    def pega(i):
        return v[i] if len(v) > i else None
    base = dict(PH_AGUA=pega(0), PH_KCL=pega(1))
    # Pontua cada leitura: 2 por fechar S, 1 por fechar T. A ficha pode não
    # fechar T (erro dela, `PE_027`); aí decide S. Empate → leitura normal.
    nota_normal = (2 * fecha(v[2:6], pega(6)) if len(v) > 6 else 0) +         (fecha([pega(6), pega(7), pega(8)], pega(9)) if len(v) > 9 else 0)
    nota_somado = (2 * fecha(v[2:5], pega(5)) if len(v) > 5 else 0) +         (fecha([pega(5), pega(6), pega(7)], pega(8)) if len(v) > 8 else 0)
    normal = nota_normal == 3
    if nota_normal >= nota_somado:
        base.update(CA_TROC=pega(2), MG_TROC=pega(3), K_TROC=pega(4),
                    NA_TROC=pega(5), AL_TROC=pega(7), H_TROC=pega(8),
                    P_ASSIM=pega(12))
        aviso = None if normal else             "complexo sortivo não fecha S e T na leitura normal; mantida por ser a mais plausível"
        return base, aviso
    base.update(CA_TROC=None, MG_TROC=None, K_TROC=pega(3), NA_TROC=pega(4),
                AL_TROC=pega(6), H_TROC=pega(7), P_ASSIM=pega(11),
                _CA_MG_SOMADOS=pega(2))
    return base, "Ca²⁺ e Mg²⁺ somados numa célula"


def transcrever(texto: str) -> dict:
    """Ficha em texto → {'HORIZONTES': [...], '_AVISOS': [...], ...}."""
    avisos: list[str] = []
    horizontes = _morfologia(texto)
    if not horizontes:
        return {"HORIZONTES": [], "_AVISOS": ["nenhuma linha morfológica reconhecida"]}
    tabelas = _tabelas(texto)

    granulo = _parear(horizontes, tabelas.get("granulometria", []), avisos, "granulometria")
    for h, linha in zip(horizontes, granulo):
        if not linha:
            continue
        v = [numero(x) for x in linha[2:]]
        if tabelas["_variante_granulometria"] == "areia total":
            h.update(SILTE=v[4] if len(v) > 4 else None,
                     ARGILA=v[5] if len(v) > 5 else None,
                     _AREIA_TOTAL=v[3] if len(v) > 3 else None)
        else:
            h.update(AREIA_GROS=v[3] if len(v) > 3 else None,
                     AREIA_FINA=v[4] if len(v) > 4 else None,
                     SILTE=v[5] if len(v) > 5 else None,
                     ARGILA=v[6] if len(v) > 6 else None)

    complexo = _parear(horizontes, tabelas.get("complexo", []), avisos, "complexo")
    for h, linha in zip(horizontes, complexo):
        if not linha:
            continue
        campos, aviso = _complexo(linha[1:])
        h.update(campos)
        if aviso:
            avisos.append(f"{h['SIMB_HORIZ']}: {aviso}")

    carbono = _parear(horizontes, tabelas.get("carbono", []), avisos, "carbono")
    for h, linha in zip(horizontes, carbono):
        if not linha:
            continue
        v = [numero(x) for x in linha[1:]]
        h.update(C_ORG=v[0] if v else None,
                 TEOR_FE=v[5] if len(v) > 5 else None,
                 TEOR_P=v[7] if len(v) > 7 else None,
                 EQUI_CACO3=v[13] if len(v) > 13 else None)

    sodio = _parear(horizontes, tabelas.get("sodio", []), avisos, "sódio")
    for h, linha in zip(horizontes, sodio):
        if not linha:
            continue
        v = [numero(x) for x in linha[1:]]
        h.update(COND_ELETR=v[1] if len(v) > 1 else None)

    m = re.search(r"^CLASSIFICAÇÃO\s+(.+(?:\n\s.+)?)", texto, re.M)
    classificacao = re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    return {"HORIZONTES": horizontes, "_AVISOS": avisos,
            "_CLASSIFICACAO_FICHA": classificacao}
