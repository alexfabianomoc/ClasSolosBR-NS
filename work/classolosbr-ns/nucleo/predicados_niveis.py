"""Predicados derivados dos níveis 2 e 3 (SiBCS 5ª ed., 2018).

Registrados em `horizontes.PREDICADOS` ao importar `niveis5`. Cada um devolve
(V3, detalhe) e segue a regra de três valores do núcleo: falta de dado capaz
de decidir → indeterminado, nunca falso.

Páginas citadas são as **impressas** da 5ª edição (página do PDF + 2),
conferidas no texto extraído do PDF em 2026-10-15.
"""

from __future__ import annotations

from .horizontes import (leitura_atual, requisito_espessura_chernozemico,
                         atende_espessura, gs, horizontes_do_tipo,
                         principal)
from .logica import F, I, V
from .perfil import Perfil


def _num(h, nome):
    x = h.get(nome)
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _sufixos(h) -> list[str]:
    moderno = leitura_atual(h.simbolo)
    return [s.rstrip(gs.MACRON) for s in gs.analisa(moderno or h.simbolo).sufixos]


def _principal_completo(h) -> str:
    moderno = leitura_atual(h.simbolo)
    return gs.analisa(moderno or h.simbolo).principal or ""


# ------------------------------------------------------------ A húmico ------

def a_humico(perfil: Perfil):
    """Horizonte A húmico — 5ª ed., Cap. 2, p. 51.

    Valor e croma úmidos ≤ 4 e V < 65%; espessura mínima do A chernozêmico;
    C orgânico abaixo do limite do hístico (80 g/kg, p. 49); e
    Σ(CO × espessura em dm) dos sub-horizontes A ≥ 60 + 0,1 × argila média
    ponderada do horizonte superficial, incluindo AB ou AC.
    """
    a = [h for h in perfil.horizontes if principal(h) == "A"]
    if not a:
        return F, "sem horizonte A"
    sup = [h for h in perfil.horizontes
           if principal(h) == "A" or _principal_completo(h) in ("AB", "AC")]
    falta = []
    for h in a:
        valor, croma, v_pct, co = (_num(h, "COR_UMIDA_VALOR"), _num(h, "COR_UMIDA_CROMA"),
                                   _num(h, "V_PERCENT"), _num(h, "C_ORG"))
        if valor is not None and valor > 4 or croma is not None and croma > 4:
            return F, f"{h.simbolo}: cor {valor}/{croma} acima de 4"
        if v_pct is not None and v_pct >= 65:
            return F, f"{h.simbolo}: V = {v_pct:.0f}%, não inferior a 65%"
        if co is not None and co >= 80:
            return F, f"{h.simbolo}: C = {co:g} g/kg, teor de hístico"
        if None in (valor, croma, v_pct, co) or h.espessura is None:
            falta.append(h.simbolo)
    espessura = sum(h.espessura or 0 for h in a)
    # 16º defeito (2026-10-17): "espessura mínima como a descrita para o
    # horizonte A chernozêmico" — o mesmo requisito do item (e), com o terço.
    brando, exigente, regra = requisito_espessura_chernozemico(perfil)
    if not falta and not atende_espessura(espessura, brando):
        return F, f"A com {espessura:g} cm, abaixo do exigido ({regra})"
    if falta:
        return I, "dado incompleto no A: " + ", ".join(falta)
    if not atende_espessura(espessura, exigente):
        return I, f"A com {espessura:g} cm, na faixa que a norma não decide ({regra})"
    co_total = sum(_num(h, "C_ORG") * h.espessura / 10 for h in a)
    pesos = [(h.espessura, _num(h, "ARGILA")) for h in sup]
    if any(e is None or arg is None for e, arg in pesos):
        return I, "argila ou espessura ausente no horizonte superficial"
    argila = sum(e * arg for e, arg in pesos) / sum(e for e, _ in pesos)
    limite = 60 + 0.1 * argila
    if co_total >= limite:
        return V, f"Σ CO×dm = {co_total:.0f} ≥ {limite:.0f}"
    return F, f"Σ CO×dm = {co_total:.0f} < {limite:.0f}"


# ------------------------------------------------- Latossolos Brunos --------

def latossolo_bruno_cor(perfil: Perfil):
    """Cor da parte superior do B (inclusive BA), Latossolos Brunos, p. 195.

    Matiz 7,5YR ou mais amarelo com valor ≤ 4 e croma ≤ 6; ou matiz 5YR com
    valor ≤ 4 e croma < 6. "Parte superior" lida como o primeiro horizonte de
    principal B, inclusive BA.
    """
    bs = [h for h in perfil.horizontes if principal(h) == "B"]
    if not bs:
        return F, "sem horizonte B"
    h = bs[0]
    m, v, c = _num(h, "MATIZ_NUM"), _num(h, "COR_UMIDA_VALOR"), _num(h, "COR_UMIDA_CROMA")
    if None in (m, v, c):
        return I, f"{h.simbolo}: cor úmida incompleta"
    ok = (m >= 17.5 and v <= 4 and c <= 6) or (m == 15 and v <= 4 and c < 6)
    return (V if ok else F), f"{h.simbolo}: matiz {m:g}, {v:g}/{c:g}"


def carbono_ate_70(perfil: Perfil):
    """"Conteúdo de carbono orgânico superior a 10 g kg-1 até 70 cm", p. 195.

    ⚠️ Lido como: todo horizonte que começa acima de 70 cm tem C > 10 g/kg.
    """
    alvo = [h for h in perfil.horizontes
            if h.limite_sup is not None and h.limite_sup < 70]
    if not alvo:
        return I, "sem horizonte nos primeiros 70 cm"
    vals = [(_num(h, "C_ORG"), h.simbolo) for h in alvo]
    if any(c is not None and c <= 10 for c, _ in vals):
        return F, "C ≤ 10 g/kg antes de 70 cm"
    if any(c is None for c, _ in vals):
        return I, "C orgânico ausente antes de 70 cm"
    return V, "C > 10 g/kg até 70 cm"


# -------------------------------------------------------- Luvissolos --------

def solum_maior_que_80(perfil: Perfil):
    """Pálicos — espessura do solum (A + B, inclusive E e exclusive BC) > 80 cm.

    Luvissolos, p. 214.
    """
    soma, falta = 0.0, []
    for h in perfil.horizontes:
        p = principal(h)
        if p not in ("A", "E", "B"):
            continue
        if _principal_completo(h) in ("BC", "CB"):
            continue
        if h.espessura is None:
            falta.append(h.simbolo)
            continue
        soma += h.espessura
    if soma > 80:
        return V, f"solum de {soma:g} cm"
    if falta:
        return I, f"solum de {soma:g} cm sem a espessura de {', '.join(falta)}"
    return F, f"solum de {soma:g} cm"


# ------------------------------------------------------ Espodossolos --------

def _espodicos(perfil):
    return horizontes_do_tipo(perfil, "B espódico")


def espodico_humiluvico(perfil: Perfil):
    """Humilúvicos — B espódico identificado com Bh e/ou Bhm, p. 165.

    "Principalmente" lido como: existe B espódico com `h` e sem `s`.
    """
    esp = _espodicos(perfil)
    if not esp:
        return I, "nenhum B espódico identificado"
    achou = [h.simbolo for h in esp if "h" in _sufixos(h) and "s" not in _sufixos(h)]
    return (V, ", ".join(achou)) if achou else (F, "nenhum Bh/Bhm")


def espodico_ferriluvico(perfil: Perfil):
    """Ferrilúvicos — B espódico identificado com Bs e/ou Bsm, p. 165."""
    esp = _espodicos(perfil)
    if not esp:
        return I, "nenhum B espódico identificado"
    achou = [h.simbolo for h in esp if "s" in _sufixos(h) and "h" not in _sufixos(h)]
    return (V, ", ".join(achou)) if achou else (F, "nenhum Bs/Bsm")


def _topo_espodico(perfil):
    topos = [h.limite_sup for h in _espodicos(perfil) if h.limite_sup is not None]
    return min(topos) if topos else None


def espodico_200_400(perfil: Perfil):
    """B espódico a profundidade > 200 cm e ≤ 400 cm, p. 166."""
    t = _topo_espodico(perfil)
    if t is None:
        return I, "profundidade do B espódico desconhecida"
    return (V if 200 < t <= 400 else F), f"B espódico a {t:g} cm"


def espodico_ate_200(perfil: Perfil):
    """B espódico a profundidade ≤ 200 cm, p. 166."""
    t = _topo_espodico(perfil)
    if t is None:
        return I, "profundidade do B espódico desconhecida"
    return (V if t <= 200 else F), f"B espódico a {t:g} cm"


def saturado_com_agua(perfil: Perfil):
    """"Permanecem saturados com água [...] na maioria dos anos", p. 166.

    ⚠️ Não há medida de saturação no contrato. Usa-se a drenagem, pela nota
    da própria norma: "a intenção é separar [...] solos mal e muito mal
    drenados" — códigos 7 e 8 do contrato.
    """
    d = perfil.drenagem
    if d is None:
        return I, "drenagem não informada"
    return (V if d >= 7 else F), f"drenagem {d:g}"


def _hidromorfia(perfil: Perfil, com_mosqueado: bool):
    for h in perfil.horizontes:
        if h.limite_sup is None or h.limite_sup > 100:
            continue
        p, suf = principal(h), _sufixos(h)
        if p == "H":
            return V, f"{h.simbolo}: horizonte H"
        if p == "E" and "g" in suf:
            return V, f"{h.simbolo}: horizonte Eg"
        if com_mosqueado and p in ("E", "B") and h.get("COR_MOSQ_VALOR_1") is not None:
            return V, f"{h.simbolo}: mosqueado"
    # Acumulação de manganês (e de ferro, nos ferri) não está no contrato:
    # a ausência do que se vê não refuta o que não se registra.
    return I, "sem H hístico nem Eg; acumulação de Mn/Fe não registrada no contrato"


def hidromorfia_humiluvico(perfil: Perfil):
    """(a) H hístico e/ou (b) Eg ou acumulação de Mn no E/B espódico ≤ 100 cm."""
    return _hidromorfia(perfil, com_mosqueado=False)


def hidromorfia_ferri(perfil: Perfil):
    """(a) H hístico e/ou (b) Eg, mosqueados ou acumulação de Fe/Mn ≤ 100 cm."""
    return _hidromorfia(perfil, com_mosqueado=True)


PREDICADOS_NIVEIS = {
    "horizonte A húmico": a_humico,
    "cor brunada na parte superior do B (Latossolos Brunos)": latossolo_bruno_cor,
    "carbono orgânico > 10 g/kg até 70 cm": carbono_ate_70,
    "solum (A + B, inclusive E, exclusive BC) > 80 cm": solum_maior_que_80,
    "B espódico com Bh/Bhm": espodico_humiluvico,
    "B espódico com Bs/Bsm": espodico_ferriluvico,
    "B espódico entre 200 e 400 cm": espodico_200_400,
    "B espódico até 200 cm": espodico_ate_200,
    "saturado com água (mal ou muito mal drenado)": saturado_com_agua,
    "H hístico ou Eg até 100 cm": hidromorfia_humiluvico,
    "H hístico, Eg ou mosqueado até 100 cm": hidromorfia_ferri,
}
