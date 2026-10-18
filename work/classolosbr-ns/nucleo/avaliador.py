"""O avaliador — percorre as regras (que são dados) e registra a derivação.

Produz, numa única passagem, as quatro estruturas de que a arquitetura
depende:

* **árvore de prova** — a derivação da classe atribuída;
* **árvore de falha** — a derivação das classes refutadas, com o nó exato que
  falhou (insumo do Explicador de Divergências, §4.3);
* **distância ao limiar** — em cada nó de comparação falho, quanto faltou;
  é sobre ela que a abdução contrastiva calcula a alteração mínima;
* **conjunto de classes alcançáveis** — as que a norma não refutou por falta
  de evidência (Avaliador Parcial, §4.2.4).

A propriedade que sustenta o componente: nenhuma classe é descartada sem que a
norma a descarte, logo o conjunto alcançável **contém** a classe verdadeira.
Ela decorre das tabelas de `logica.py` e não depende de dado nem de ajuste.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import product

from .horizontes import (horizontes_do_tipo, horizontes_indeterminados_do_tipo,
                         tem_b_diagnostico)
from .logica import F, I, V, V3, e3, nao3, ou3
from .perfil import Horizonte, Perfil
from . import regras as r

_OPERADORES = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


@dataclass
class Derivacao:
    """Um nó do registro da avaliação."""

    rotulo: str
    valor: V3
    detalhe: str = ""
    #: Quanto faltou para satisfazer, na unidade do atributo. Só em nós de
    #: comparação falhos. É o insumo direto da abdução contrastiva.
    distancia: float | None = None
    atributo: str | None = None
    horizonte: str | None = None
    fonte: str = ""
    #: Operador e limiar da comparação falha, e posição do horizonte em
    #: `perfil.horizontes`. Só em nós de comparação falhos. Permitem ao
    #: Explicador (§4.3) calcular o valor que inverteria o predicado sem
    #: reler a regra. `indice` é `None` quando o horizonte não pertence ao
    #: perfil consultado.
    operador: str | None = None
    limiar: float | None = None
    indice: int | None = None
    filhos: list["Derivacao"] = field(default_factory=list)

    def texto(self, nivel: int = 0, so_falhas: bool = False) -> str:
        """Renderiza a árvore. `so_falhas` poda os ramos verdadeiros."""
        if so_falhas and self.valor is V and not self.filhos:
            return ""
        marca = {V: "✓", F: "✗", I: "?"}[self.valor]
        linha = "  " * nivel + f"{marca} {self.rotulo}"
        if self.detalhe:
            linha += f" — {self.detalhe}"
        if self.distancia is not None:
            linha += f"  [falta {self.distancia:g}]"
        partes = [linha]
        for f_ in self.filhos:
            sub = f_.texto(nivel + 1, so_falhas)
            if sub:
                partes.append(sub)
        return "\n".join(partes)

    def folhas_falhas(self) -> list["Derivacao"]:
        """Nós falhos sem filhos falhos — os pontos de ruptura."""
        if self.valor is not F:
            return []
        abaixo = [n for f_ in self.filhos for n in f_.folhas_falhas()]
        return abaixo or [self]


@dataclass
class Resultado:
    """A saída do núcleo para um perfil."""

    perfil: str
    classe: str | None
    derivacao: Derivacao | None
    alcancaveis: list[str] = field(default_factory=list)
    refutadas: list[tuple[str, Derivacao]] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)

    @property
    def conclusivo(self) -> bool:
        return self.classe is not None and not self.alcancaveis

    def resumo(self) -> str:
        if self.classe and not self.alcancaveis:
            return self.classe
        if self.classe:
            return (f"{self.classe} (não conclusivo — também alcançável: "
                    f"{', '.join(self.alcancaveis)})")
        if self.alcancaveis:
            return "indeterminado — alcançáveis: " + ", ".join(self.alcancaveis)
        return "nenhuma classe do recorte se aplica"


# ------------------------------------------------------------ avaliação -----

def avaliar(condicao, perfil: Perfil) -> Derivacao:
    """Avalia uma condição contra um perfil e devolve o registro."""
    if isinstance(condicao, r.E):
        filhos = [avaliar(p, perfil) for p in condicao.partes]
        return Derivacao("E", e3(f.valor for f in filhos),
                         fonte=condicao.fonte, filhos=filhos)

    if isinstance(condicao, r.Ou):
        filhos = [avaliar(p, perfil) for p in condicao.partes]
        return Derivacao("OU", ou3(f.valor for f in filhos),
                         fonte=condicao.fonte, filhos=filhos)

    if isinstance(condicao, r.Nao):
        filho = avaliar(condicao.parte, perfil)
        return Derivacao("NÃO", nao3(filho.valor),
                         fonte=condicao.fonte, filhos=[filho])

    if isinstance(condicao, r.Pendente):
        return Derivacao(f"pendente: {condicao.motivo}", I,
                         detalhe="dado não disponível no contrato",
                         fonte=condicao.fonte)

    if isinstance(condicao, r.Residual):
        return Derivacao("classe residual", V,
                         detalhe="as classes anteriores foram refutadas",
                         fonte=condicao.fonte)

    if isinstance(condicao, r.Derivado):
        from .horizontes import PREDICADOS
        funcao = PREDICADOS.get(condicao.predicado)
        if funcao is None:
            raise KeyError(f"predicado não registrado: {condicao.predicado}")
        valor, detalhe = funcao(perfil)
        return Derivacao(condicao.predicado, valor, detalhe=detalhe,
                         fonte=condicao.fonte)

    if isinstance(condicao, r.Existe):
        return _existe(condicao, perfil)

    if isinstance(condicao, r.Compara):
        return _compara(condicao, perfil)

    if isinstance(condicao, r.Booleano):
        return _booleano(condicao, perfil)

    raise TypeError(f"condição não reconhecida: {type(condicao).__name__}")


def _selecionar(seletor: r.Seletor, perfil: Perfil,
                indeterminados: bool = False) -> list[Horizonte]:
    """Horizontes que o seletor alcança.

    Com `indeterminados=True`, devolve os que o símbolo propõe como o tipo
    pedido com veto pendente (ver `Identificacao.indeterminada`) — os que
    tornam a condição indeterminada, e não verdadeira.
    """
    if indeterminados:
        if not seletor.tipo:
            return []
        if seletor.tipo == "B diagnóstico":
            # B cujo tipo o símbolo não diz (2026-10-15): pode ser qualquer
            # B diagnóstico, e "existe B diagnóstico" fica indeterminado.
            from .horizontes import b_indeterminados
            candidatos = b_indeterminados(perfil)
        else:
            candidatos = horizontes_indeterminados_do_tipo(perfil, seletor.tipo)
    elif seletor.tipo == "B diagnóstico":
        candidatos = [
            h for h in perfil.horizontes
            if tem_b_diagnostico(Perfil(perfil.id_ponto, [h]))
        ]
    elif seletor.tipo:
        candidatos = horizontes_do_tipo(perfil, seletor.tipo)
    else:
        candidatos = list(perfil.horizontes)

    if seletor.principal:
        candidatos = [
            h for h in candidatos
            if __import__("nucleo.horizontes", fromlist=["principal"]).principal(h)
            == seletor.principal
        ]
    if seletor.inicio_ate_cm is not None:
        candidatos = [
            h for h in candidatos
            if h.limite_sup is not None and h.limite_sup <= seletor.inicio_ate_cm
        ]
    if seletor.primeiro:
        candidatos = candidatos[:1]
    return candidatos


def _existe(condicao: r.Existe, perfil: Perfil) -> Derivacao:
    def posicionados(achados):
        if not condicao.imediatamente_abaixo_de:
            return achados
        from .horizontes import principais_possiveis
        aceitos = []
        for h in achados:
            acima = _acima_ignorando_transicionais(perfil, h)
            # Opção (b), 2026-10-16: com símbolo antigo ambíguo (`A3` → `AB`
            # ou `EB`), basta que todas as leituras ponham a letra principal
            # no conjunto pedido.
            if acima is not None and principais_possiveis(acima) <= set(
                    condicao.imediatamente_abaixo_de):
                aceitos.append(h)
        return aceitos

    detalhe_adj = (" imediatamente abaixo de "
                   + "/".join(condicao.imediatamente_abaixo_de)
                   if condicao.imediatamente_abaixo_de else "")
    rotulo = "existe " + condicao.onde.descricao() + detalhe_adj

    achados = posicionados(_selecionar(condicao.onde, perfil))
    if achados:
        return Derivacao(rotulo, V,
                         detalhe=", ".join(h.simbolo for h in achados),
                         horizonte=achados[0].simbolo, fonte=condicao.fonte)
    # Décimo primeiro defeito (2026-10-14): horizonte que o símbolo propõe e
    # que o dado ainda poderia vetar torna a condição indeterminada, e não
    # falsa nem verdadeira.
    pendentes = posicionados(_selecionar(condicao.onde, perfil, indeterminados=True))
    if pendentes:
        return Derivacao(rotulo, I,
                         detalhe=(", ".join(h.simbolo for h in pendentes)
                                  + ": identificação com veto pendente"),
                         horizonte=pendentes[0].simbolo, fonte=condicao.fonte)
    return Derivacao(rotulo, F, detalhe="nenhum horizonte satisfaz",
                     fonte=condicao.fonte)


def _acima_ignorando_transicionais(perfil: Perfil, h: Horizonte):
    """O primeiro horizonte não transicional acima de `h`.

    "Imediatamente abaixo do horizonte A" não é rompido por um `AB`, `BA`,
    `A/B` ou `B/A` interposto: transicionais são a passagem entre os dois
    horizontes que nomeiam, e a norma os lê como parte dela.

    ⚠️ Defeito corrigido em 2026-09-07: sem esta tolerância,
    `GeoTab_PE_031_Itambe` (A1 A2 A3 A4 A/B B/A Bw) não era reconhecido como
    Latossolo — o `Bw` tinha o `B/A` logo acima, e a adjacência falhava.
    """
    from sentinela import gramatica_sufixos as gs
    from .horizontes import leituras_atuais
    atual = h
    while True:
        acima = perfil.acima_de(atual)
        if acima is None:
            return None
        # Opção (b), 2026-10-16: o símbolo é lido em notação atual, e é
        # transicional quando **todas** as leituras o são (`A3` → `AB` ou
        # `EB`; `B1t` → `BAt` ou `BEt`; `B3t` → `BCt`). Antes, o símbolo cru
        # era analisado, e a notação de 1962 nunca contava como transicional.
        analises = [gs.analisa(x) for x in leituras_atuais(acima.simbolo)]
        transicional = all(a.transicional or a.mesclado for a in analises)
        if not transicional:
            return acima
        atual = acima


def _compara(condicao: r.Compara, perfil: Perfil) -> Derivacao:
    alvos = _selecionar(condicao.onde, perfil)
    rotulo = (f"{condicao.atributo} {condicao.operador} "
              f"{condicao.limiar:g}{(' ' + condicao.unidade) if condicao.unidade else ''}"
              f" em {condicao.onde.descricao()}")

    if not alvos:
        return Derivacao(rotulo, I, detalhe="nenhum horizonte selecionado",
                         atributo=condicao.atributo, fonte=condicao.fonte)

    teste = _OPERADORES[condicao.operador]
    valores, faltantes, satisfeitos, distancias = [], [], [], []
    for h in alvos:
        valor = h.get(condicao.atributo)
        if valor is None:
            faltantes.append(h.simbolo)
            continue
        valores.append((h, float(valor)))
        if teste(float(valor), condicao.limiar):
            satisfeitos.append(h)
        else:
            distancias.append((h, abs(condicao.limiar - float(valor))))

    if not valores:
        return Derivacao(rotulo, I,
                         detalhe=f"atributo ausente em {', '.join(faltantes)}",
                         atributo=condicao.atributo,
                         horizonte=faltantes[0] if faltantes else None,
                         fonte=condicao.fonte)

    if condicao.agregacao == "maior parte":
        return _maior_parte(condicao, rotulo, valores, satisfeitos, faltantes,
                            alvos)

    if condicao.agregacao == "todos":
        ok = not distancias
    else:
        ok = bool(satisfeitos)

    if ok:
        h, v = next((hv for hv in valores if hv[0] in satisfeitos), valores[0])
        return Derivacao(rotulo, V, detalhe=f"{condicao.atributo}({h.simbolo})={v:g}",
                         atributo=condicao.atributo, horizonte=h.simbolo,
                         fonte=condicao.fonte)

    # Falso, mas com dado faltando em parte dos horizontes: a evidência é
    # incompleta e não se refuta.
    if faltantes and condicao.agregacao == "qualquer":
        return Derivacao(rotulo, I,
                         detalhe=f"não satisfeito nos medidos; ausente em "
                                 f"{', '.join(faltantes)}",
                         atributo=condicao.atributo, fonte=condicao.fonte)

    h, dist = min(distancias, key=lambda hd: hd[1])
    valor = h.get(condicao.atributo)
    indice = next((i for i, x in enumerate(perfil.horizontes) if x is h), None)
    return Derivacao(rotulo, F,
                     detalhe=f"{condicao.atributo}({h.simbolo})={float(valor):g}",
                     distancia=dist, atributo=condicao.atributo,
                     horizonte=h.simbolo, fonte=condicao.fonte,
                     operador=condicao.operador, limiar=condicao.limiar,
                     indice=indice)


def _peso(condicao, alvos, h) -> float:
    """Espessura de `h` que conta para a agregação.

    Sem seção de controle declarada, é a espessura do horizonte. Com ela, é a
    interseção com os primeiros N cm contados do topo do primeiro horizonte
    selecionado — a leitura literal de "os primeiros 100 cm do horizonte B".
    """
    limite = condicao.onde.seccao_controle_cm
    if limite is None:
        return h.espessura or 0.0
    topos = [a.limite_sup for a in alvos if a.limite_sup is not None]
    if not topos:
        return h.espessura or 0.0
    topo = min(topos)
    return h.sobrepoe(topo, topo + limite)


def _maior_parte(condicao, rotulo, valores, satisfeitos, faltantes,
                 alvos) -> Derivacao:
    """Decide por espessura, e devolve indeterminado no empate.

    O empate não é caso de borda inventado: é o perfil `GeoTab_RN_007_Acu`,
    com metade do horizonte B de argila de atividade alta e metade de baixa.
    O sistema de referência devolve `unknown` para ele, e a 6ª edição do SiBCS
    creditou ao SmartSolos a identificação dessa lacuna da própria norma —
    que continua sem regra de desempate.

    Aqui o mesmo perfil produz **indeterminado com motivo**: a classe fica
    alcançável, e o texto diz que a norma não decide. É a diferença entre
    `unknown` e um diagnóstico.
    """
    espessura_ok = sum(_peso(condicao, alvos, h) for h in satisfeitos)
    total = sum(_peso(condicao, alvos, h) for h, _ in valores)
    if total <= 0:
        return Derivacao(rotulo, I, detalhe="espessuras desconhecidas",
                         atributo=condicao.atributo, fonte=condicao.fonte)
    fracao = espessura_ok / total
    detalhe = (f"{espessura_ok:g} de {total:g} cm satisfazem "
               f"({100 * fracao:.0f}%)")
    if faltantes:
        detalhe += f"; atributo ausente em {', '.join(faltantes)}"
        return Derivacao(rotulo, I, detalhe=detalhe,
                         atributo=condicao.atributo, fonte=condicao.fonte)
    if fracao > 0.5:
        return Derivacao(rotulo, V, detalhe=detalhe,
                         atributo=condicao.atributo, fonte=condicao.fonte)
    if abs(fracao - 0.5) < 1e-9:
        return Derivacao(
            rotulo, I,
            detalhe=detalhe + " — empate exato; a norma exige 'a maior parte' "
                              "e não prevê desempate",
            atributo=condicao.atributo, fonte=condicao.fonte)
    return Derivacao(rotulo, F, detalhe=detalhe,
                     atributo=condicao.atributo, fonte=condicao.fonte)


def _booleano(condicao: r.Booleano, perfil: Perfil) -> Derivacao:
    alvos = _selecionar(condicao.onde, perfil)
    rotulo = f"{condicao.atributo} é {condicao.esperado} em {condicao.onde.descricao()}"
    if not alvos:
        return Derivacao(rotulo, I, detalhe="nenhum horizonte selecionado",
                         atributo=condicao.atributo, fonte=condicao.fonte)
    vistos = [h for h in alvos if h.get(condicao.atributo) is not None]
    if not vistos:
        return Derivacao(rotulo, I, detalhe="caráter não informado",
                         atributo=condicao.atributo, fonte=condicao.fonte)
    casou = [h for h in vistos if bool(h.get(condicao.atributo)) is condicao.esperado]
    if casou:
        return Derivacao(rotulo, V, detalhe=casou[0].simbolo,
                         atributo=condicao.atributo, horizonte=casou[0].simbolo,
                         fonte=condicao.fonte)
    return Derivacao(rotulo, F, detalhe="nenhum horizonte apresenta o caráter",
                     atributo=condicao.atributo, fonte=condicao.fonte)


# --------------------------------------------------------- classificação ----

def classificar(perfil: Perfil, chave=None) -> Resultado:
    """Percorre a chave na ordem de precedência e devolve o resultado.

    A primeira regra satisfeita determina a classe — é o comportamento da
    chave. Regras avaliadas como indeterminadas **antes** dela não são
    ignoradas: cada uma é uma classe que a norma não refutou, e que teria
    precedência sobre a atribuída. Por isso entram em `alcancaveis`, e o
    resultado é declarado não conclusivo.
    """
    if chave is None:
        # A edição de produção é a 5ª (`edicoes.EDICAO_PADRAO`). Até
        # 2026-10-14 o padrão aqui era a 6ª, resto do desenho anterior; todas
        # as chamadas passavam a chave explícita, e o risco era latente.
        from .chave5 import CHAVE_5ED
        chave = CHAVE_5ED

    alcancaveis: list[str] = []
    refutadas: list[tuple[str, Derivacao]] = []
    pendencias: list[str] = []
    variantes = _variantes_de_leitura(perfil)

    for regra in chave:
        derivacao = _avaliar_por_leitura(regra.condicao, perfil, variantes)
        derivacao.rotulo = f"{regra.classe}: {derivacao.rotulo}"
        derivacao.fonte = derivacao.fonte or regra.fonte

        if derivacao.valor is V:
            return Resultado(perfil.id_ponto, regra.classe, derivacao,
                             alcancaveis, refutadas, pendencias)
        if derivacao.valor is I:
            alcancaveis.append(regra.classe)
            pendencias.extend(
                n.rotulo for n in _nos_indeterminados(derivacao)
            )
        else:
            refutadas.append((regra.classe, derivacao))

    return Resultado(perfil.id_ponto, None, None, alcancaveis,
                     refutadas, pendencias)


#: Limite de combinações de leituras avaliadas num perfil (2 leituras por
#: horizonte ambíguo; acima disso, a avaliação por leitura seria cara).
MAX_VARIANTES = 16


#: Limiares de saturação por bases usados pelas regras (5ª e 6ª ed.): 50%
#: (eutrófico, saturação alta, caráter alumínico) e 65% (A chernozêmico,
#: A húmico). Conferido por busca em `nucleo/` em 2026-10-17; um limiar novo
#: de V tem de entrar aqui.
LIMIARES_V = (50.0, 65.0)


def _v_em_conflito(h: Horizonte) -> float | None:
    """O V do boletim, se ele e o calculado caem em lados opostos de um limiar."""
    calc, bol = h.get("V_PERCENT"), h.get("_V_BOLETIM")
    if not isinstance(calc, (int, float)) or not isinstance(bol, (int, float)):
        return None
    if any((float(calc) >= L) != (float(bol) >= L) for L in LIMIARES_V):
        return float(bol)
    return None


def _com_v(h: Horizonte, v_pct: float) -> Horizonte:
    from .perfil import _derivados_niveis
    atributos = {**h.atributos, "V_PERCENT": v_pct}
    novo = replace(h, atributos=atributos)
    atributos.update(_derivados_niveis(novo, atributos))
    return novo


def _variantes_de_leitura(perfil: Perfil) -> list[Perfil]:
    """Uma cópia do perfil por combinação de leituras dos símbolos ambíguos
    e das duas versões de V nos horizontes em que cálculo e boletim
    discordam no limiar.

    🚨 Decisão 2, opção (c), do usuário (2026-10-17). Quando o V calculado de
    S/T e o V informado no boletim caem em lados opostos de 50% ou de 65%, o
    mesmo laudo sustenta as duas conclusões: arredondamento do laboratório
    (64,6 publicado como 65) ou erro de transcrição num dos campos. O núcleo
    não escolhe: avalia as duas versões e combina como nas leituras do
    símbolo — o que não depende do V sai como antes; o que depende sai I.

    🚨 Opção (b), decisão do usuário de 2026-10-16. Quando as traduções de um
    símbolo antigo **discordam** (`A3cn` → `ABcn` ou `EBcn`), o símbolo não
    diz se o horizonte pertence ao A ou ao E, e regras que dependem disso —
    o A chernozêmico, a adjacência — podem mudar de valor. Tratar o horizonte
    como "nem A nem E" afirmaria o que o símbolo não sustenta: na primeira
    implementação, quatro perfis do BDSolos com `A1cn`–`A3cn` concluíam
    Neossolo assim. Avalia-se então cada leitura, e `_avaliar_por_leitura`
    combina: V se todas dão V, F se todas dão F, I se divergem.

    Perfis sem símbolo de leituras discordantes devolvem `[perfil]`, e a
    avaliação é exatamente a de antes.
    """
    from .horizontes import _leituras_discordam, gs
    eixos = []                      # (índice, [transformações do horizonte])
    for i, h in enumerate(perfil.horizontes):
        opcoes = [lambda x: x]
        if _leituras_discordam(h.simbolo):
            opcoes = [lambda x, s=s: replace(x, simbolo=s) for s in gs.leituras(h.simbolo)]
        bol = _v_em_conflito(h)
        if bol is not None:
            opcoes = [t for o in opcoes for t in (o, lambda x, o=o, b=bol: _com_v(o(x), b))]
        if len(opcoes) > 1:
            eixos.append((i, opcoes))
    if not eixos:
        return [perfil]
    variantes = []
    for combinacao in product(*(opcoes for _, opcoes in eixos)):
        if len(variantes) >= MAX_VARIANTES:
            break
        horizontes = list(perfil.horizontes)
        for (i, _), transforma in zip(eixos, combinacao):
            horizontes[i] = transforma(horizontes[i])
        variantes.append(replace(perfil, horizontes=horizontes))
    return variantes


def _avaliar_por_leitura(condicao, perfil: Perfil, variantes: list[Perfil]) -> Derivacao:
    """Avalia a condição em cada leitura e combina por supervalorização."""
    if len(variantes) == 1:
        return avaliar(condicao, variantes[0])
    derivacoes = [avaliar(condicao, v) for v in variantes]
    valores = {d.valor for d in derivacoes}
    base = derivacoes[0]
    if len(valores) == 1:
        return base
    from .horizontes import _leituras_discordam, gs
    causas = []
    ambiguos = [h.simbolo for h in perfil.horizontes if _leituras_discordam(h.simbolo)]
    if ambiguos:
        causas.append("da leitura do símbolo antigo ("
                      + "; ".join(f"{s}: {' ou '.join(gs.leituras(s))}" for s in ambiguos) + ")")
    conflitos = [(h.simbolo, h.get("V_PERCENT"), _v_em_conflito(h)) for h in perfil.horizontes
                 if _v_em_conflito(h) is not None]
    if conflitos:
        causas.append("do V, que cálculo e boletim põem em lados opostos do limiar ("
                      + "; ".join(f"{s}: {c:.1f}% calculado, {b:g}% no boletim"
                                  for s, c, b in conflitos) + ")")
    base.valor = I
    base.detalhe = ((base.detalhe + " — ") if base.detalhe else "") + (
        "o valor depende " + " e ".join(causas) + " — indeterminado")
    return base


def _nos_indeterminados(no: Derivacao) -> list[Derivacao]:
    if no.valor is not I:
        return []
    abaixo = [n for f_ in no.filhos for n in _nos_indeterminados(f_)]
    return abaixo or [no]
