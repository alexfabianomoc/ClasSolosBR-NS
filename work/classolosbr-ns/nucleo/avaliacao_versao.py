"""Camada de Versão por pares de perfis (monografia, Quadro 7 e §5.9; D-3 da
auditoria de 2026-10-17).

    python -m nucleo.avaliacao_versao

Para cada diferença normativa de primeiro nível documentada entre as bases
(`edicoes.DIFERENCAS_DOCUMENTADAS`), um perfil isola a diferença, e o que se
espera de cada base é o que **a norma** prevê — escrito no caso, com a
passagem, antes de executar. A medida é a proporção das diferenças para as
quais as duas bases se comportam como a norma prevê: divergindo onde a
passagem da 5ª para a 6ª muda a classe, e não divergindo onde a diferença de
texto não muda o desfecho (por exemplo, quando a precedência da 6ª já
captura o perfil que a exclusão da 5ª encaminhava).

A medida avalia a **implementação** contra a leitura da norma registrada
aqui; ela não verifica a leitura. Perfis são sintéticos, salvo onde
indicado: o caso do Planossolo usa um perfil real do conjunto curado, porque
construir um horizonte B plânico sintético exigiria inventar atributos que o
contrato não descreve. Um caso que o contrato de entrada não permite montar
é contado como não avaliável, e não como reproduzido.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

from .avaliacao import PYKKA7
from .avaliador import Resultado, classificar
from .chave5 import CHAVE_5ED
from .chave6 import CHAVE_6ED
from .estatistica import fmt, wilson
from .perfil import Horizonte, Perfil, carregar_json


def h(simbolo, sup, inf, matiz="10YR", valor=4, croma=4, **extra) -> Horizonte:
    """Horizonte com cor, granulometria e complexo sortivo plausíveis."""
    d = {"COR_UMIDA_MATIZ": matiz, "COR_UMIDA_VALOR": valor, "COR_UMIDA_CROMA": croma,
         "ARGILA": 200, "SILTE": 150, "AREIA_GROS": 350, "AREIA_FINA": 300,
         "C_ORG": 5, "V_PERCENT": 30, "ESTRUTURA_GRAU": 2, "CTC": 8}
    d.update(extra)
    return Horizonte(simbolo, sup, inf, d)


def conclui(classe):
    def f(r: Resultado):
        return r.conclusivo and r.classe == classe
    f.__doc__ = f"conclui {classe}"
    return f


def nao_conclui_com(*classes):
    def f(r: Resultado):
        alc = set(r.alcancaveis) | ({r.classe} if r.classe else set())
        return not r.conclusivo and set(classes) <= alc
    f.__doc__ = "não conclui; alcançáveis incluem " + ", ".join(classes)
    return f


def refuta(classe):
    def f(r: Resultado):
        return classe != r.classe and classe not in r.alcancaveis
    f.__doc__ = f"refuta {classe}"
    return f


def nao_refuta(classe):
    def f(r: Resultado):
        return classe == r.classe or classe in r.alcancaveis
    f.__doc__ = f"não refuta {classe}"
    return f


@dataclass
class Caso:
    diferenca: str
    passagem: str
    diverge: bool          # a norma prevê saídas diferentes entre as edições?
    perfil: Callable[[], Perfil | None]
    esperado5: Callable[[Resultado], bool]
    esperado6: Callable[[Resultado], bool]
    nota: str = ""
    obtido: dict = field(default_factory=dict)


def _real(caminho):
    def f():
        return carregar_json(PYKKA7 / caminho)[0]
    return f


CASOS = [
    Caso("precedência da chave e posição do B textural nos Argissolos",
         "5ª, Cap. 4, p. 111-114 (Cambissolos antes dos Argissolos; B textural "
         "'imediatamente abaixo'); 6ª, Cap. 4, p. 121-123, e Cap. 5, p. 125 "
         "('subjacente a', nos primeiros 200 cm) × Cap. 3, p. 97",
         True,
         lambda: Perfil("par-Bi-sobre-Bt", [
             h("A", 0, 20, ARGILA=120, SILTE=100, AREIA_GROS=400, AREIA_FINA=380),
             h("Bi", 20, 60, ARGILA=150, SILTE=100, AREIA_GROS=400, AREIA_FINA=350),
             h("BC", 60, 105, ARGILA=200, SILTE=100, AREIA_GROS=350, AREIA_FINA=350),
             h("Bt", 105, 160, ARGILA=400, SILTE=100, AREIA_GROS=250, AREIA_FINA=250)]),
         conclui("CAMBISSOLO"), nao_conclui_com("ARGISSOLO", "CAMBISSOLO"),
         "a 6ª é internamente inconsistente; a base devolve as duas leituras"),
    Caso("posição do B textural nos Luvissolos",
         "5ª, Cap. 4 ('imediatamente abaixo'); 6ª, chave e Cap. 11, p. 221 "
         "('subjacente a') × Cap. 3, p. 105",
         True,
         lambda: Perfil("par-Luvissolo-Bt-a-60", [
             h("A", 0, 20, ARGILA=150),
             h("Bi", 20, 60, ARGILA=180),
             h("Bt", 60, 120, ARGILA=400, ATIVIDADE_ARGILA=40, V_PERCENT=80)]),
         conclui("CAMBISSOLO"), nao_conclui_com("LUVISSOLO")),
    Caso("glei ocupando a maior parte dos 30 cm abaixo do A (só na 6ª)",
         "5ª, Cap. 9, p. 175 (glei dentro de 50 cm); 6ª, p. 101",
         True,
         lambda: Perfil("par-glei-com-lacuna", [
             h("Ap", 0, 15, "10YR", 5, 1),
             h("Cg1", 30, 50, "2.5Y", 6, 2),
             h("Cg2", 70, 85, "2.5Y", 6, 2)]),
         conclui("GLEISSOLO"), nao_conclui_com("GLEISSOLO")),
    Caso("seção da exclusão textural dos Gleissolos (150 cm na 5ª, 200 cm na 6ª)",
         "5ª, Cap. 9, p. 175; 6ª, Cap. 9",
         True,
         lambda: Perfil("par-glei-arenoso-ate-160", [
             h("A", 0, 20, "10YR", 4, 1, ARGILA=50, SILTE=30, AREIA_GROS=600, AREIA_FINA=320),
             h("Cg1", 20, 90, "5Y", 6, 1, ARGILA=50, SILTE=30, AREIA_GROS=600, AREIA_FINA=320),
             h("Cg2", 90, 160, "5Y", 6, 1, ARGILA=50, SILTE=30, AREIA_GROS=600, AREIA_FINA=320),
             h("Cg3", 160, 210, "5Y", 6, 1, ARGILA=350, SILTE=200, AREIA_GROS=250, AREIA_FINA=200)]),
         refuta("GLEISSOLO"), nao_refuta("GLEISSOLO"),
         "na 5ª, todos os horizontes até 150 cm são arenosos e a classe é "
         "excluída; na 6ª, a seção vai a 200 cm e inclui o horizonte argiloso"),
    Caso("cor do horizonte que precede o plíntico na condição (b)",
         "5ª, p. 104 e 261 (10YR com croma ≤ 4); 6ª, p. 269 (valor ≥ 5)",
         True,
         lambda: Perfil("par-precedente-10YR-4-3", [
             h("A", 0, 20, "2.5YR", 5, 4),
             h("C", 20, 60, "10YR", 4, 3, C_ORG=1),
             h("Cf", 60, 120, "10YR", 7, 2, C_ORG=1),
             h("C2", 120, 170, "2.5YR", 4, 6, C_ORG=1)]),
         nao_refuta("PLINTOSSOLO"), refuta("PLINTOSSOLO"),
         "o 10YR 4/3 é pálido pela 5ª e não pela 6ª, que exige valor ≥ 5; o "
         "plíntico começa a 60 cm, fora da condição dos 40 cm"),
    Caso("concrecionário em solo sem B diagnóstico (Neossolos)",
         "5ª, p. 96-97, 104 e 219 (só o Conceito e a Abrangência o excluem); "
         "6ª, p. 227",
         True,
         lambda: Perfil("par-concrecionario", [
             h("A", 0, 20, "10YR", 4, 3, C_ORG=8),
             h("Cc", 20, 70, "10YR", 4, 3, C_ORG=2),
             h("C", 70, 120, "10YR", 4, 3, C_ORG=1)]),
         nao_conclui_com("NEOSSOLO", "PLINTOSSOLO"), conclui("PLINTOSSOLO")),
    Caso("B plânico coincidente com o horizonte plíntico (Planossolos)",
         "5ª, Cap. 4 (exclusão só na 5ª)",
         True,
         _real("RN/json/GeoTab_RN_044_Mossoro.json"),
         conclui("PLINTOSSOLO"), nao_conclui_com("PLINTOSSOLO", "PLANOSSOLO"),
         "perfil real do conjunto curado"),
    Caso("lista de exclusões dos Neossolos (5ª) × cláusula residual (6ª)",
         "5ª, Cap. 3, p. 96, e Cap. 12, p. 219; 6ª, 13ª posição",
         False,
         lambda: Perfil("par-A-C", [
             h("A", 0, 20, "10YR", 4, 3, C_ORG=6),
             h("C", 20, 120, "10YR", 6, 4, C_ORG=1)]),
         conclui("NEOSSOLO"), conclui("NEOSSOLO"),
         "a exclusão migrou da prosa para a ordem: mesmo desfecho"),
    Caso("plíntico nos Cambissolos (exclusão só na 5ª)",
         "5ª, Cap. 4 (Plintossolos testados depois dos Cambissolos)",
         False,
         lambda: Perfil("par-Bif", [
             h("A", 0, 20, "2.5YR", 5, 4, C_ORG=6),
             h("Bif", 20, 80, "10YR", 7, 2, C_ORG=1, ARGILA=250),
             h("C", 80, 130, "2.5YR", 4, 6, C_ORG=1)]),
         conclui("PLINTOSSOLO"), conclui("PLINTOSSOLO"),
         "na 6ª a precedência dos Plintossolos já captura o perfil"),
    Caso("plíntico nos Gleissolos (exclusão só na 5ª)",
         "5ª, Cap. 4 e Cap. 9, p. 175",
         False,
         lambda: Perfil("par-glei-sobre-plintico", [
             h("A", 0, 15, "10YR", 4, 1, C_ORG=6),
             h("Cg", 15, 30, "5Y", 6, 1, C_ORG=1),
             h("Cf", 30, 90, "10YR", 7, 2, C_ORG=1),
             h("C", 90, 140, "2.5YR", 4, 6, C_ORG=1)]),
         conclui("PLINTOSSOLO"), conclui("PLINTOSSOLO"),
         "na 6ª a precedência dos Plintossolos já captura o perfil"),
    Caso("Gleissolos e Neossolos em solo arenoso com glei até 200 cm",
         "5ª, p. 96, requisito (a) dos Neossolos (glei não exclui em textura "
         "areia ou areia franca) e p. 175 (exclusão textural dos Gleissolos); "
         "6ª, exclusão textural a 200 cm e Neossolos como classe residual",
         False,
         lambda: Perfil("par-glei-arenoso-ate-200", [
             h("A", 0, 20, "10YR", 4, 1, ARGILA=50, SILTE=30, AREIA_GROS=600, AREIA_FINA=320),
             h("Cg1", 20, 100, "5Y", 6, 1, ARGILA=50, SILTE=30, AREIA_GROS=600, AREIA_FINA=320),
             h("Cg2", 100, 210, "5Y", 6, 1, ARGILA=50, SILTE=30, AREIA_GROS=600, AREIA_FINA=320)]),
         nao_refuta("NEOSSOLO"), nao_refuta("NEOSSOLO"),
         "acrescentado depois de ler a árvore de prova do caso anterior, que "
         "mostrou a regra da 5ª refutando o Neossolo pelo glei sem a exceção da "
         "textura arenosa; o esperado é o da norma, não o do código"),
    Caso("contato lítico nos primeiros 30 cm (Vertissolos, só na 5ª)",
         "5ª, Cap. 4, requisito (c)",
         True,
         lambda: Perfil("par-vertico-raso", [
             h("A", 0, 10, "10YR", 3, 2, ARGILA=450, C_ORG=8),
             h("Cv", 10, 25, "10YR", 4, 2, ARGILA=500, C_ORG=2),
             h("R", 25, 60)]),
         refuta("VERTISSOLO"), nao_refuta("VERTISSOLO"),
         "o horizonte vértico depende de atributos que o contrato não traz; a "
         "6ª só pode deixá-lo pendente"),
]


def avaliar_caso(c: Caso) -> tuple[bool | None, Resultado | None, Resultado | None]:
    p = c.perfil()
    if p is None:
        return None, None, None
    r5, r6 = classificar(p, CHAVE_5ED), classificar(p, CHAVE_6ED)
    return c.esperado5(r5) and c.esperado6(r6), r5, r6


def main(argv=None) -> int:
    print("Camada de Versão — pares por diferença normativa de 1º nível")
    print("=" * 78)
    ok = 0
    linhas = []
    for c in CASOS:
        sucesso, r5, r6 = avaliar_caso(c)
        ok += bool(sucesso)
        linhas.append((c, sucesso, r5, r6))
        marca = "ok  " if sucesso else "FALHA"
        print(f"\n{marca} {c.diferenca}  ({'diverge' if c.diverge else 'não diverge'} pela norma)")
        print(f"      norma: {c.passagem}")
        print(f"      esperado 5ª: {c.esperado5.__doc__}; 6ª: {c.esperado6.__doc__}")
        print(f"      obtido   5ª: {r5.resumo()}; 6ª: {r6.resumo()}")
        if c.nota:
            print(f"      nota: {c.nota}")
    n = len(CASOS)
    div = [x for x in linhas if x[0].diverge]
    print(f"\nreproduzidas como a norma prevê: {ok}/{n} {fmt(wilson(ok, n))}"
          f" — com divergência prevista {sum(1 for x in div if x[1])}/{len(div)},"
          f" sem divergência prevista {sum(1 for x in linhas if not x[0].diverge and x[1])}"
          f"/{n - len(div)}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
