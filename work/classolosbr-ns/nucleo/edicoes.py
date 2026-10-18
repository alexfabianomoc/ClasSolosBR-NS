"""Camada versão-consciente (M3) — classifica sob as duas edições e compara.

O ClasSolosBR-NS5 tem a **5ª edição como base de produção**: é a edição sob a
qual o sistema de referência ([[smartsolos-expert]]) responde e sob a qual os
dois acervos disponíveis foram rotulados. A base da 6ª edição (`chave6.py`)
permanece no núcleo e é a **contraprova**: rodar o mesmo perfil nas duas e
comparar é o que transforma "a classe divergiu" em um diagnóstico com causa
nomeada.

O módulo tem duas funções (monografia, seção 4.2.3, reescrita em 2026-10-14):

1. **diagnóstico** — quando a classe derivada diverge da registrada e as duas
   bases concordam entre si, a mudança de edição fica **excluída** como causa;
   restam erro de dado e erro de formalização **comum às duas bases**, que o
   cotejo não distingue (o Explicador e a leitura da norma distinguem). Quando
   as bases divergem entre si, a classe do perfil é sensível à edição;
2. **auditoria** — num acervo rotulado sob a 5ª, aponta os rótulos que
   deixariam de valer sob a 6ª.

⚠️ A versão anterior desta docstring listava "três causas", sendo a terceira
(erro na base) a "divergência que o cotejo não explica" — caso vazio por
construção, porque as bases ou concordam ou divergem, e que atribuía ao dado o
erro de formalização comum às duas bases (foi o caso do nono defeito).

⚠️ O módulo compara **implementações**, não edições. Uma divergência entre
`chave5.py` e `chave6.py` só é evidência sobre a norma na medida em que as duas
bases difiram apenas onde as edições diferem — princípio declarado no cabeçalho
de `chave5.py` e que se degrada em silêncio se alguém editar uma das duas sem
olhar a outra. `assimetrias()` existe para tornar isso verificável.
"""

from __future__ import annotations

from dataclasses import dataclass

from .avaliador import (Resultado, _avaliar_por_leitura,
                        _variantes_de_leitura, classificar)
from .logica import I, V3
from .chave5 import CHAVE_5ED
from .chave6 import CHAVE_6ED
from .perfil import Perfil

#: A edição de produção do NS5. Trocar aqui muda o padrão de todo o sistema.
EDICAO_PADRAO = "5"

CHAVES = {
    "5": CHAVE_5ED,
    "6": CHAVE_6ED,
}

ROTULO = {
    "5": "SiBCS 5ª ed. (2018)",
    "6": "SiBCS 6ª ed. (2025)",
}


def chave_de(edicao: str = EDICAO_PADRAO):
    """Devolve a base de regras de uma edição, ou explode com o que existe."""
    try:
        return CHAVES[str(edicao)]
    except KeyError:
        disponiveis = ", ".join(sorted(CHAVES))
        raise ValueError(
            f"edição {edicao!r} não implementada; disponíveis: {disponiveis}"
        ) from None


#: Causas da não conclusão de uma base, por classe alcançável. A atribuição é
#: mecânica e não lê a norma: compara o valor da mesma regra nas duas bases.
EXCLUSIVA = "critério em que as bases diferem"
COMUM = "dado insuficiente para critério comum às duas bases"
COBERTURA = "ordem apenas triada (cobertura incompleta ou dado ausente, não distinguidos)"


def valores_por_classe(perfil: Perfil, chave) -> dict[str, V3]:
    """Valor (V, F, I) da condição de **cada** classe da chave, sem parar na
    primeira verdadeira, pela mesma avaliação por leitura de `classificar`."""
    variantes = _variantes_de_leitura(perfil)
    return {r.classe: _avaliar_por_leitura(r.condicao, perfil, variantes).valor
            for r in chave}


@dataclass(frozen=True)
class Cotejo:
    """O resultado do mesmo perfil sob as duas edições.

    🚨 Revisto em 2026-10-17 (auditoria da monografia, item I-1). Antes,
    `divergem` comparava só a classe, e o ramo "as duas edições concordam"
    dizia "a divergência NÃO se explica por edição" também quando as duas
    bases apenas não concluíam e a classe registrada seguia alcançável — 12
    dos 94 perfis curados, nenhum deles divergente. E toda não conclusão era
    dita "possivelmente de cobertura", sem distinguir cobertura, dado
    insuficiente para critério comum e dado insuficiente para critério em que
    as bases diferem. Agora as saídas se comparam por classe, grau de
    conclusão e conjunto alcançável, e cada classe que impede a conclusão
    recebe uma causa, pela comparação do valor da mesma regra nas duas bases.
    A causa "critério em que as bases diferem" só é evidência sobre a norma
    na medida em que as bases difiram apenas onde as edições diferem
    (`assimetrias`, `diferencas_nao_documentadas`).
    """

    perfil: str
    sob_5a: Resultado
    sob_6a: Resultado
    valores_5a: dict | None = None
    valores_6a: dict | None = None

    @property
    def divergem(self) -> bool:
        """As saídas diferem: na classe, no grau de conclusão ou no conjunto
        alcançável."""
        def saida(r):
            return (r.classe, r.conclusivo, frozenset(r.alcancaveis))
        return saida(self.sob_5a) != saida(self.sob_6a)

    @property
    def ambas_conclusivas(self) -> bool:
        return self.sob_5a.conclusivo and self.sob_6a.conclusivo

    def causas(self, edicao: str) -> dict[str, str]:
        """Para a base indicada ("5" ou "6"), a causa de cada classe
        alcançável que impede a conclusão."""
        res, meus, outros, chave = (
            (self.sob_5a, self.valores_5a, self.valores_6a, CHAVE_5ED)
            if edicao == "5" else
            (self.sob_6a, self.valores_6a, self.valores_5a, CHAVE_6ED))
        if res.conclusivo or meus is None or outros is None:
            return {}
        no_recorte = {r.classe: r.no_recorte for r in chave}
        causas = {}
        for classe in res.alcancaveis:
            outro = outros.get(classe)
            if outro is not None and outro is not I:
                causas[classe] = EXCLUSIVA
            elif not no_recorte.get(classe, False):
                causas[classe] = COBERTURA
            else:
                causas[classe] = COMUM
        return causas

    def diagnostico(self, classe_registrada: str | None = None) -> str:
        """Traduz o cotejo na linguagem do problema, não na do código."""
        reg = classe_registrada

        def alcanca(r):
            return reg is not None and (reg == r.classe or reg in r.alcancaveis)

        partes = []
        if not self.divergem:
            partes.append(f"as duas edições dão a mesma saída: {self.sob_5a.resumo()}")
        else:
            partes.append(f"saídas diferentes — 5ª: {self.sob_5a.resumo()}; "
                          f"6ª: {self.sob_6a.resumo()}")
        for ed, res in (("5ª", self.sob_5a), ("6ª", self.sob_6a)):
            causas = self.causas(ed[0])
            if causas:
                partes.append(f"a {ed} não conclui por " + "; ".join(
                    f"{c} ({motivo})" for c, motivo in causas.items()))
        if reg is None:
            return " — ".join(partes)

        r5, r6 = self.sob_5a, self.sob_6a
        if r5.conclusivo and r6.conclusivo:
            if r5.classe == r6.classe:
                partes.append(
                    f"a ficha registra {reg}" + (
                        "" if reg == r5.classe else
                        " — divergência que a passagem da 5ª para a 6ª não "
                        "explica; segue ao Explicador"))
            elif reg == r5.classe:
                partes.append(f"a ficha registra {reg}, a classe da 5ª — "
                              "rótulo válido sob a 5ª e sensível à 6ª")
            elif reg == r6.classe:
                partes.append(f"a ficha registra {reg}, a classe da 6ª — "
                              "ficha já atualizada")
            else:
                partes.append(f"a ficha registra {reg}, que não é a classe de "
                              "nenhuma das duas — segue ao Explicador")
            return " — ".join(partes)

        a5, a6 = alcanca(r5), alcanca(r6)
        for ed, r, outra, o in (("5ª", r5, "6ª", r6), ("6ª", r6, "5ª", r5)):
            if r.conclusivo and r.classe == reg and alcanca(o):
                partes.append(f"a ficha registra {reg}, concluída na {ed} e só "
                              f"alcançável, sem conclusão, na {outra} — rótulo "
                              f"válido sob a {ed}, não confirmado sob a {outra}")
                return " — ".join(partes)
        if a5 and a6:
            partes.append(f"a ficha registra {reg}, alcançável nas duas — "
                          "incompletude, e não divergência")
        elif a5 or a6:
            ed = "5ª" if a5 else "6ª"
            partes.append(f"a ficha registra {reg}, alcançável só na {ed}")
        else:
            partes.append(f"a ficha registra {reg}, fora do alcançável nas duas — "
                          "divergência que a passagem da 5ª para a 6ª não "
                          "explica; segue ao Explicador")
        return " — ".join(partes)


def cotejar(perfil: Perfil) -> Cotejo:
    """Classifica o perfil sob as duas edições."""
    return Cotejo(
        perfil=perfil.id_ponto,
        sob_5a=classificar(perfil, CHAVE_5ED),
        sob_6a=classificar(perfil, CHAVE_6ED),
        valores_5a=valores_por_classe(perfil, CHAVE_5ED),
        valores_6a=valores_por_classe(perfil, CHAVE_6ED),
    )


def precedencias() -> list[tuple[int, str, int, str]]:
    """Sequência das treze ordens nas duas edições, lado a lado."""
    linhas = []
    for i in range(max(len(CHAVE_5ED), len(CHAVE_6ED))):
        c5 = CHAVE_5ED[i].classe if i < len(CHAVE_5ED) else "—"
        c6 = CHAVE_6ED[i].classe if i < len(CHAVE_6ED) else "—"
        linhas.append((i + 1, c5, i + 1, c6))
    return linhas


def assimetrias() -> list[str]:
    """Diferenças de modelagem entre as duas bases, para auditá-las.

    Não acusa erro: lista o que difere, para que quem leia decida se cada
    diferença corresponde a uma diferença entre as edições ou é assimetria
    introduzida por descuido. É a salvaguarda do princípio de comparabilidade.
    """
    achados = []
    por_classe_5 = {r.classe: r for r in CHAVE_5ED}
    por_classe_6 = {r.classe: r for r in CHAVE_6ED}

    so_em_5 = sorted(set(por_classe_5) - set(por_classe_6))
    so_em_6 = sorted(set(por_classe_6) - set(por_classe_5))
    for classe in so_em_5:
        achados.append(f"{classe}: existe só na base da 5ª edição")
    for classe in so_em_6:
        achados.append(f"{classe}: existe só na base da 6ª edição")

    for classe in sorted(set(por_classe_5) & set(por_classe_6)):
        r5, r6 = por_classe_5[classe], por_classe_6[classe]
        pos5 = CHAVE_5ED.index(r5) + 1
        pos6 = CHAVE_6ED.index(r6) + 1
        if pos5 != pos6:
            achados.append(f"{classe}: posição {pos5} na 5ª, {pos6} na 6ª "
                           "(diferença de precedência — esperada)")
        if r5.no_recorte != r6.no_recorte:
            achados.append(f"⚠️ {classe}: recorte difere entre as bases "
                           f"({'fundo' if r5.no_recorte else 'triagem'} na 5ª, "
                           f"{'fundo' if r6.no_recorte else 'triagem'} na 6ª) "
                           "— assimetria de modelagem, não de norma")
        f5, f6 = _forma(r5.condicao), _forma(r6.condicao)
        if f5 != f6:
            achados.append(f"{classe}: estrutura da condição difere — "
                           f"5ª {f5}, 6ª {f6}")
    return achados


#: Toda diferença entre as bases tem de constar aqui, com a passagem da norma
#: que a justifica (2026-10-14). `diferencas_nao_documentadas()` confere as
#: duas direções: diferença sem registro e registro sem diferença. Diferença
#: nova reprova o teste até ser documentada — e, se não houver passagem que a
#: justifique, é assimetria de modelagem e deve ser desfeita.
DIFERENCAS_DOCUMENTADAS: dict[tuple[str, str], str] = {
    **{(c, "posição"): "sequência de precedência da chave das ordens — 5ª ed., Cap. 4, p. 111-114; 6ª ed., Cap. 4, p. 121-123"
       for c in ("ARGISSOLO", "CAMBISSOLO", "ESPODOSSOLO", "LUVISSOLO",
                 "NEOSSOLO", "NITOSSOLO", "PLANOSSOLO", "PLINTOSSOLO",
                 "VERTISSOLO")},
    ("ARGISSOLO", "estrutura"):
        "posição do B textural: 'imediatamente abaixo' do A ou E na 5ª; na 6ª, "
        "'subjacente a [...] nos primeiros 200 cm' no Cap. 5 (p. 125), mas "
        "'imediatamente abaixo' na Definição do Cap. 3 (p. 97) — a 6ª é "
        "internamente inconsistente, e a base devolve indeterminado onde as "
        "leituras divergem (a troca de termo está no Cap. 5 e no item "
        "Luvissolos da chave, não no item Argissolos); e o requisito (a) da "
        "Definição lista só o plíntico na 5ª (p. 87) e plíntico, "
        "concrecionário e litoplíntico na 6ª (p. 97)",
    ("LUVISSOLO", "estrutura"):
        "posição do B textural: 'imediatamente abaixo' do A ou E na 5ª; na "
        "6ª, 'subjacente a' na chave e no Cap. 11 (p. 221, com 'nos "
        "primeiros 200 cm') e 'imediatamente abaixo' na Definição do Cap. 3 "
        "(p. 105) — a base da 6ª devolve indeterminado onde divergem",
    ("CAMBISSOLO", "estrutura"):
        "exclusão do plíntico dentro de 40 cm só na 5ª, em que os "
        "Plintossolos são testados depois dos Cambissolos (5ª ed., Cap. 4)",
    ("GLEISSOLO", "estrutura"):
        "exclusão textural a 150 cm na 5ª e a 200 cm na 6ª; glei ocupando a "
        "maior parte dos 30 cm abaixo do A só na 6ª (6ª ed., p. 101); "
        "exclusão do plíntico só na 5ª (5ª ed., Cap. 4 e Cap. 9, p. 175)",
    ("NEOSSOLO", "estrutura"):
        "lista de exclusões na 5ª (Cap. 3, p. 96; Cap. 12, p. 219) × "
        "cláusula residual da 13ª posição na 6ª",
    ("PLANOSSOLO", "estrutura"):
        "não coincidência do B plânico com o horizonte plíntico só na 5ª "
        "(5ª ed., Cap. 4)",
    ("PLINTOSSOLO", "estrutura"):
        "especificação de cor do horizonte precedente na condição (b) "
        "(5ª ed., p. 104 e 261; 6ª ed., p. 269)",
    ("VERTISSOLO", "estrutura"):
        "requisito (c) — ausência de contato lítico, petrocálcico ou duripã "
        "nos primeiros 30 cm — só na 5ª (5ª ed., Cap. 4)",
}


def diferencas_nao_documentadas() -> list[str]:
    """Diferenças entre as bases sem registro, e registros sem diferença.

    Confere também que a regra de cada classe com diferença estrutural traz
    observação em ao menos uma das bases: a justificativa tem de estar na
    regra, ao alcance de quem a lê, e não só nesta lista.
    """
    por_classe_5 = {r.classe: r for r in CHAVE_5ED}
    por_classe_6 = {r.classe: r for r in CHAVE_6ED}
    encontradas: set[tuple[str, str]] = set()
    for classe in set(por_classe_5) & set(por_classe_6):
        r5, r6 = por_classe_5[classe], por_classe_6[classe]
        if CHAVE_5ED.index(r5) != CHAVE_6ED.index(r6):
            encontradas.add((classe, "posição"))
        if _forma(r5.condicao) != _forma(r6.condicao):
            encontradas.add((classe, "estrutura"))
            if not (r5.observacao or r6.observacao):
                encontradas.add((classe, "estrutura sem observação na regra"))
    problemas = [f"{c}: diferença de {t} não documentada"
                 for c, t in sorted(encontradas - set(DIFERENCAS_DOCUMENTADAS))]
    problemas += [f"{c}: registro de diferença de {t} sem diferença nas bases"
                  for c, t in sorted(set(DIFERENCAS_DOCUMENTADAS) - encontradas)]
    return problemas


def _forma(condicao) -> str:
    """Assinatura estrutural de uma condição, ignorando fontes e textos."""
    from . import regras as r

    nome = type(condicao).__name__
    if isinstance(condicao, (r.E, r.Ou)):
        return f"{nome}({', '.join(_forma(p) for p in condicao.partes)})"
    if isinstance(condicao, r.Nao):
        return f"Nao({_forma(condicao.parte)})"
    if isinstance(condicao, r.Existe):
        alvo = condicao.onde.tipo or condicao.onde.principal or "qualquer"
        adj = "+adj" if condicao.imediatamente_abaixo_de else ""
        prof = (f"+≤{condicao.onde.inicio_ate_cm:g}cm"
                if condicao.onde.inicio_ate_cm is not None else "")
        return f"Existe[{alvo}{adj}{prof}]"
    if isinstance(condicao, r.Compara):
        return (f"Compara[{condicao.atributo}{condicao.operador}"
                f"{condicao.limiar:g}]")
    if isinstance(condicao, r.Derivado):
        return f"Derivado[{condicao.predicado}]"
    return nome
