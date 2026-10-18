"""Predicados do 4º nível (subgrupos) — SiBCS 5ª ed. (2018).

Mesmo regime dos demais: (V3, detalhe), e falta de dado capaz de decidir é
indeterminado. Leituras declaradas (⚠️) quando o contrato não traz o atributo
que a norma usa e há um substituto observável.
"""

from __future__ import annotations

from .horizontes import gs, horizontes_do_tipo, leitura_atual, principal, relacao_textural
from .logica import F, I, V
from .perfil import INDETERMINADA, Perfil


def _num(h, nome):
    x = h.get(nome)
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _sufixos(h):
    moderno = leitura_atual(h.simbolo)
    return [s.rstrip(gs.MACRON) for s in gs.analisa(moderno or h.simbolo).sufixos]


def _profundidade_observada(perfil) -> float | None:
    fundos = []
    for h in perfil.horizontes:
        if h.limite_inf is not None and h.limite_inf < INDETERMINADA:
            fundos.append(h.limite_inf)
        elif h.limite_inf_observado is not None:
            fundos.append(h.limite_inf_observado)
        elif h.limite_sup is not None:
            fundos.append(h.limite_sup)
    return max(fundos) if fundos else None


# ------------------------------------------------- textura arenosa ----------

def _arenosa_ate(perfil):
    """Profundidade até onde a textura é arenosa desde a superfície.

    (profundidade, completo): `completo` é falso quando um horizonte sem
    granulometria interrompe a leitura antes de achar o fim da textura
    arenosa.
    """
    fundo = 0.0
    for h in perfil.horizontes:
        if h.limite_sup is None or h.limite_sup < 0:
            continue
        a = h.get("ARENOSA")
        if a is None:
            return fundo, False
        if not a:
            return h.limite_sup, True
        fim = h.limite_inf if (h.limite_inf is not None and h.limite_inf < INDETERMINADA) \
            else h.limite_inf_observado
        if fim is None:
            return h.limite_sup, False
        fundo = fim
    return fundo, False


def _arenosa_entre(perfil, minimo, maximo, rotulo):
    prof, completo = _arenosa_ate(perfil)
    if completo:
        return (V if minimo <= prof <= maximo else F), f"arenosa até {prof:g} cm"
    if prof > maximo:
        return F, f"arenosa além de {maximo:g} cm"
    return I, f"arenosa até ao menos {prof:g} cm; {rotulo}"


def arenosa_50_100(perfil: Perfil):
    """Textura arenosa da superfície até no mínimo 50 e no máximo 100 cm (arênicos)."""
    return _arenosa_entre(perfil, 50, 100, "granulometria incompleta")


def arenosa_100_200(perfil: Perfil):
    """Textura arenosa da superfície até > 100 e ≤ 200 cm (espessarênicos)."""
    prof, completo = _arenosa_ate(perfil)
    if completo:
        return (V if 100 < prof <= 200 else F), f"arenosa até {prof:g} cm"
    if prof > 200:
        return F, f"arenosa além de 200 cm"
    return I, f"arenosa até ao menos {prof:g} cm"


def _topo_espodico(perfil):
    t = [h.limite_sup for h in horizontes_do_tipo(perfil, "B espódico") if h.limite_sup is not None]
    return min(t) if t else None


def _arenosa_ate_espodico(perfil, minimo, maximo, estrito_min):
    topo = _topo_espodico(perfil)
    if topo is None:
        return I, "topo do B espódico desconhecido"
    dentro = (minimo < topo <= maximo) if estrito_min else (minimo <= topo <= maximo)
    if not dentro:
        return F, f"B espódico a {topo:g} cm"
    acima = [h for h in perfil.horizontes
             if h.limite_sup is not None and 0 <= h.limite_sup < topo]
    vals = [h.get("ARENOSA") for h in acima]
    if any(v == 0.0 for v in vals):
        return F, "horizonte não arenoso acima do B espódico"
    if any(v is None for v in vals):
        return I, "granulometria ausente acima do B espódico"
    return V, f"arenosa até o B espódico, a {topo:g} cm"


def arenosa_ate_espodico_50_100(perfil: Perfil):
    """Arenosa da superfície até o B espódico, que começa de 50 a 100 cm."""
    return _arenosa_ate_espodico(perfil, 50, 100, estrito_min=False)


def arenosa_ate_espodico_100_200(perfil: Perfil):
    """Arenosa da superfície até o B espódico, que começa a > 100 e ≤ 200 cm."""
    return _arenosa_ate_espodico(perfil, 100, 200, estrito_min=True)


# -------------------------------------------------------- contatos ----------

def _contato(perfil, minimo, maximo):
    """Contato lítico (horizonte R) com topo em (minimo, maximo]."""
    rs = [h for h in perfil.horizontes if principal(h) == "R" and h.limite_sup is not None]
    if rs:
        topo = min(h.limite_sup for h in rs)
        return (V if minimo < topo <= maximo else F), f"R a {topo:g} cm"
    prof = _profundidade_observada(perfil)
    if prof is not None and prof >= maximo:
        return F, f"sem R até {prof:g} cm"
    return I, "perfil descrito acima da profundidade do critério, sem R"


def contato_litico_ate_50(perfil: Perfil):
    """Contato lítico dentro de 50 cm (líticos). Lido no horizonte R."""
    return _contato(perfil, -1, 50)


def contato_litico_50_100(perfil: Perfil):
    """Contato lítico a > 50 e ≤ 100 cm (lépticos). Lido no horizonte R."""
    return _contato(perfil, 50, 100)


def _fragmentario(perfil, minimo, maximo):
    """⚠️ Contato lítico fragmentário: o contrato tem `FRAGMENTARIO`, sem
    semântica documentada. Verdadeiro num horizonte com topo na janela →
    V; nos demais casos, indeterminado (não se refuta com campo de sentido
    incerto)."""
    for h in perfil.horizontes:
        if h.get("FRAGMENTARIO") is True and h.limite_sup is not None \
                and minimo < h.limite_sup <= maximo:
            return V, f"{h.simbolo}: FRAGMENTARIO"
    return I, "contato lítico fragmentário não registrado de forma inequívoca"


def fragmentario_ate_50(perfil: Perfil):
    return _fragmentario(perfil, -1, 50)


def fragmentario_50_100(perfil: Perfil):
    return _fragmentario(perfil, 50, 100)


def saprolitico(perfil: Perfil):
    """Horizonte Cr e ausência de contato lítico ou lítico fragmentário,
    todos dentro de 100 cm (saprolíticos)."""
    crs = [h for h in perfil.horizontes
           if h.limite_sup is not None and h.limite_sup <= 100
           and gs.analisa(leitura_atual(h.simbolo) or h.simbolo).principal == "C"
           and "r" in _sufixos(h)]
    if not crs:
        return F, "sem horizonte Cr até 100 cm"
    r = [h for h in perfil.horizontes
         if principal(h) == "R" and h.limite_sup is not None and h.limite_sup <= 100]
    if r:
        return F, f"contato lítico a {r[0].limite_sup:g} cm"
    if any(h.get("FRAGMENTARIO") is True and h.limite_sup is not None
           and h.limite_sup <= 100 for h in perfil.horizontes):
        return F, "contato lítico fragmentário até 100 cm"
    return V, f"{crs[0].simbolo} a {crs[0].limite_sup:g} cm, sem contato lítico"


# ------------------------------------------------- feições por sufixo -------

def _sufixo_ate(perfil, letra, limite, tipos=()):
    for h in perfil.horizontes:
        if h.limite_sup is None or h.limite_sup > limite:
            continue
        if letra in _sufixos(h):
            return V, f"{h.simbolo}: sufixo {letra}"
    for t in tipos:
        for h in horizontes_do_tipo(perfil, t):
            if h.limite_sup is not None and h.limite_sup <= limite:
                return V, f"{h.simbolo}: {t}"
    return F, f"sem sufixo {letra} até {limite:g} cm"


def plintico_ate_150(perfil: Perfil):
    """Caráter plíntico ou horizonte plíntico dentro de 150 cm.

    ⚠️ Caráter plíntico exige ≥ 5% de plintita (p. 36), que o contrato não
    traz; lido no sufixo `f` (presença de plintita, Larach et al., 1988).
    """
    return _sufixo_ate(perfil, "f", 150, ("plíntico",))


def plintico_ate_200(perfil: Perfil):
    return _sufixo_ate(perfil, "f", 200, ("plíntico",))


def _petro(perfil, limite):
    for h in perfil.horizontes:
        if h.limite_sup is None or h.limite_sup > limite:
            continue
        if h.get("LITOPLINTICO") is True or h.get("PETROPLINTICO") is True:
            return V, f"{h.simbolo}: litoplíntico/petroplíntico"
    for t in ("concrecionário", "litoplíntico"):
        for h in horizontes_do_tipo(perfil, t):
            if h.limite_sup is not None and h.limite_sup <= limite:
                return V, f"{h.simbolo}: {t}"
    return F, f"sem concrecionário ou litoplíntico até {limite:g} cm"


def petroplintico_ate_150(perfil: Perfil):
    """Caracteres ou horizontes concrecionário e/ou litoplíntico ≤ 150 cm."""
    return _petro(perfil, 150)


def petroplintico_ate_200(perfil: Perfil):
    return _petro(perfil, 200)


def latossolico_abaixo_textural(perfil: Perfil):
    """B latossólico abaixo do B textural dentro de 150 cm (latossólicos)."""
    bts = [h.limite_sup for h in horizontes_do_tipo(perfil, "B textural") if h.limite_sup is not None]
    bws = [h.limite_sup for h in horizontes_do_tipo(perfil, "B latossólico") if h.limite_sup is not None]
    if not bts:
        return F, "sem B textural"
    ok = [w for w in bws if w > min(bts) and w <= 150]
    return (V, f"B latossólico a {ok[0]:g} cm") if ok else (F, "sem B latossólico abaixo do B textural até 150 cm")


def redoxico_50_150(perfil: Perfil):
    """Caráter redóxico a > 50 e ≤ 150 cm, lido no booleano REDOXICO do contrato."""
    vistos = False
    for h in perfil.horizontes:
        if h.limite_sup is None or not (50 < h.limite_sup <= 150):
            continue
        x = h.get("REDOXICO")
        if x is True:
            return V, f"{h.simbolo}: redóxico"
        vistos = vistos or x is not None
    return (F, "nenhum horizonte redóxico entre 50 e 150 cm") if vistos else (I, "REDOXICO não informado")


# -------------------------------------------------- B textural, RT ---------

def _rt(perfil):
    return relacao_textural(perfil)


def rt_maior_que_1_5(perfil: Perfil):
    rt = _rt(perfil)
    if rt is None:
        return I, "relação textural não calculável"
    return (V if rt > 1.5 else F), f"RT = {rt:.2f}"


def rt_maior_igual_1_4(perfil: Perfil):
    rt = _rt(perfil)
    if rt is None:
        return I, "relação textural não calculável"
    return (V if rt >= 1.4 else F), f"RT = {rt:.2f}"


def cerosidade_nitica_em_b(perfil: Perfil):
    """Morfologia semelhante aos Nitossolos: cerosidade ≥ comum e moderada
    num horizonte B (critério do B nítico, Cap. 2)."""
    vistos = False
    for h in perfil.horizontes:
        if principal(h) != "B":
            continue
        q, g = _num(h, "CEROSIDADE_QUANTIDADE"), _num(h, "CEROSIDADE_GRAU")
        if q is None or g is None:
            continue
        vistos = True
        if q >= 2 and g >= 3:
            return V, f"{h.simbolo}: cerosidade {q:g}/{g:g}"
    return (F, "cerosidade abaixo de comum e moderada no B") if vistos else (I, "cerosidade não informada no B")


def estrutura_argiluvica(perfil: Perfil):
    """B com estrutura prismática em qualquer grau ou em blocos ≥ moderada (p. 33)."""
    vistos = False
    for h in perfil.horizontes:
        if principal(h) != "B":
            continue
        tipo, grau = _num(h, "ESTRUTURA_TIPO"), _num(h, "ESTRUTURA_GRAU")
        if tipo is None:
            continue
        vistos = True
        if tipo == 2 or (tipo in (4, 5) and grau is not None and grau >= 3):
            return V, f"{h.simbolo}: estrutura {tipo:g}/{grau}"
    return (F, "sem estrutura prismática ou em blocos ≥ moderada no B") if vistos else (I, "estrutura não informada")


def blocos_moderada_cerosidade_fraca(perfil: Perfil):
    """B (exclusive BA) com blocos moderada e cerosidade pouca e fraca ≤ 200 cm.

    ⚠️ "pouca e fraca" lida como "ao menos pouca e ao menos fraca".
    """
    vistos = False
    for h in perfil.horizontes:
        if principal(h) != "B" or (gs.analisa(leitura_atual(h.simbolo) or h.simbolo).principal == "BA"):
            continue
        if h.limite_sup is None or h.limite_sup > 200:
            continue
        tipo, grau = _num(h, "ESTRUTURA_TIPO"), _num(h, "ESTRUTURA_GRAU")
        q, g = _num(h, "CEROSIDADE_QUANTIDADE"), _num(h, "CEROSIDADE_GRAU")
        if None in (tipo, grau, q, g):
            continue
        vistos = True
        if tipo in (4, 5) and grau >= 3 and q >= 1 and g >= 2:
            return V, f"{h.simbolo}"
    return (F, "sem blocos moderada com cerosidade no B") if vistos else (I, "estrutura ou cerosidade não informadas")


def carbono_10_ate_80(perfil: Perfil):
    """Carbono ≥ 10 g/kg até 80 cm ou mais (espesso-húmicos).

    ⚠️ Lido como: todo horizonte que começa acima de 80 cm tem C ≥ 10 g/kg.
    """
    alvo = [h for h in perfil.horizontes if h.limite_sup is not None and 0 <= h.limite_sup < 80]
    if not alvo:
        return I, "sem horizonte nos primeiros 80 cm"
    vals = [_num(h, "C_ORG") for h in alvo]
    if any(c is not None and c < 10 for c in vals):
        return F, "C < 10 g/kg antes de 80 cm"
    if any(c is None for c in vals):
        return I, "C orgânico ausente antes de 80 cm"
    return V, "C ≥ 10 g/kg até 80 cm"


PREDICADOS_SUBGRUPOS = {
    "textura arenosa da superfície até 50–100 cm": arenosa_50_100,
    "textura arenosa da superfície até 100–200 cm": arenosa_100_200,
    "arenosa até o B espódico a 50–100 cm": arenosa_ate_espodico_50_100,
    "arenosa até o B espódico a 100–200 cm": arenosa_ate_espodico_100_200,
    "contato lítico até 50 cm": contato_litico_ate_50,
    "contato lítico entre 50 e 100 cm": contato_litico_50_100,
    "contato lítico fragmentário até 50 cm": fragmentario_ate_50,
    "contato lítico fragmentário entre 50 e 100 cm": fragmentario_50_100,
    "Cr sem contato lítico até 100 cm": saprolitico,
    "caráter ou horizonte plíntico até 150 cm": plintico_ate_150,
    "caráter ou horizonte plíntico até 200 cm": plintico_ate_200,
    "concrecionário ou litoplíntico até 150 cm": petroplintico_ate_150,
    "concrecionário ou litoplíntico até 200 cm": petroplintico_ate_200,
    "B latossólico abaixo do B textural até 150 cm": latossolico_abaixo_textural,
    "caráter redóxico entre 50 e 150 cm": redoxico_50_150,
    "relação textural > 1,5": rt_maior_que_1_5,
    "relação textural ≥ 1,4": rt_maior_igual_1_4,
    "cerosidade nítica no B": cerosidade_nitica_em_b,
    "estrutura argilúvica no B": estrutura_argiluvica,
    "blocos moderada e cerosidade no B": blocos_moderada_cerosidade_fraca,
    "carbono ≥ 10 g/kg até 80 cm": carbono_10_ate_80,
}
