"""Avaliação da próxima medição do Avaliador Parcial (`nucleo.medicao`).

    python -m nucleo.avaliacao_medicao [--bdsolos N] [--json SAIDA.json]

Protocolo. Parte-se de um perfil cuja classificação é conclusiva com todos os
dados. Retiram-se três unidades de medida presentes (determinação num
horizonte: granulometria, complexo sortivo, carbono orgânico, pH, cor,
estrutura), sorteadas com semente fixa até que o resultado deixe
de ser conclusivo. Depois, "mede-se" uma unidade por vez — devolvendo os
valores verdadeiros — até o resultado voltar a ser conclusivo, com três
estratégias de ordem:

* **ganho**: a primeira candidata de `medicao.recomendar`, restrita às
  unidades retiradas (só elas têm valor verdadeiro conhecido);
* **aleatória**: média exata sobre todas as ordens das unidades retiradas;
* **topo-base**: horizontes de cima para baixo, unidades na ordem de
  `medicao.UNIDADES` — a ordem de quem preenche um formulário.

Mede-se o número de medições até concluir (de 1 a 3) e a proporção de perfis
em que a primeira medição já basta. Verificações embutidas: a classe
verdadeira tem de continuar alcançável depois de cada retirada (contenção), e
todo desfecho simulado pela recomendação tem de estar no conjunto alcançável
corrente (`medicao.Recomendacao.violacoes`).

No acervo nacional, os doadores do mesmo levantamento do perfil avaliado são
excluídos, para que a simulação não use o próprio dado.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import random
import sys
from pathlib import Path

from .avaliacao import PYKKA7
from .avaliador import classificar
from .estatistica import fmt, wilson
from .medicao import (ACOMPANHAM, DERIVADOS, UNIDADES, alcancaveis, falta,
                      recomendar)
from .perfil import _derivados, carregar_json

SEMENTE = 20261018
RETIRADAS = 3


def retirar(perfil, unidades):
    q = copy.deepcopy(perfil)
    for i, u in unidades:
        h = q.horizontes[i]
        for nome in UNIDADES[u] + ACOMPANHAM.get(u, ()) + DERIVADOS:
            h.atributos.pop(nome, None)
        h.atributos.update(_derivados(h))
    return q


def devolver(atual, original, i, u):
    q = copy.deepcopy(atual)
    h, o = q.horizontes[i], original.horizontes[i]
    for nome in UNIDADES[u] + ACOMPANHAM.get(u, ()) + DERIVADOS:
        h.atributos.pop(nome, None)
        if nome in o.atributos:
            h.atributos[nome] = o.atributos[nome]
    h.atributos.update(_derivados(h))
    return q


def passos(original, retiradas, ordem):
    """Medições, na ordem dada, até concluir; e se a contenção se manteve."""
    estado = retirar(original, retiradas)
    verdadeira = classificar(original).classe
    for n, (i, u) in enumerate(ordem, start=1):
        estado = devolver(estado, original, i, u)
        r = classificar(estado)
        if verdadeira not in alcancaveis(r):
            return n, False
        if r.conclusivo:
            return n, True
    return len(ordem), True


def caso(perfil, rng, lev=None):
    limpo = classificar(perfil)
    if not limpo.conclusivo:
        return None
    presentes = [(i, u) for i, h in enumerate(perfil.horizontes) for u in UNIDADES
                 if not falta(h, u)]
    if len(presentes) < RETIRADAS:
        return None
    for _ in range(30):
        ret = rng.sample(presentes, RETIRADAS)
        sem = classificar(retirar(perfil, ret))
        if not sem.conclusivo:
            break
    else:
        return None
    contencao = limpo.classe in alcancaveis(sem)
    # estratégia ganho: recomendação a cada passo
    estado, restantes, n_ganho, violacoes, uteis = retirar(perfil, ret), list(ret), 0, 0, 0
    while restantes:
        rec = recomendar(estado, excluir_lev=lev, so=set(restantes))
        violacoes += len(rec.violacoes)
        if not rec.candidatas:
            escolha = restantes[0]
        else:
            escolha = (rec.candidatas[0].indice, rec.candidatas[0].unidade)
            uteis += rec.candidatas[0].ganho > 0
        restantes.remove(escolha)
        estado = devolver(estado, perfil, *escolha)
        n_ganho += 1
        r = classificar(estado)
        if limpo.classe not in alcancaveis(r):
            contencao = False
        if r.conclusivo:
            break
    aleat = [passos(perfil, ret, list(o))[0] for o in itertools.permutations(ret)]
    topo = passos(perfil, ret, sorted(ret, key=lambda x: (x[0], list(UNIDADES).index(x[1]))))[0]
    return {"perfil": perfil.id_ponto, "retiradas": [[i, u] for i, u in ret],
            "alcancaveis_sem": len(alcancaveis(sem)), "ganho": n_ganho,
            "aleatoria": sum(aleat) / len(aleat), "aleatoria_1": sum(a == 1 for a in aleat) / len(aleat),
            "topo_base": topo, "contencao": contencao, "violacoes": violacoes}


def relatorio(nome, linhas):
    n = len(linhas)
    print(f"\n{nome}: {n} perfis")
    if not n:
        return {}
    g = sum(l["ganho"] for l in linhas) / n
    a = sum(l["aleatoria"] for l in linhas) / n
    t = sum(l["topo_base"] for l in linhas) / n
    g1 = sum(l["ganho"] == 1 for l in linhas)
    a1 = sum(l["aleatoria_1"] for l in linhas)
    t1 = sum(l["topo_base"] == 1 for l in linhas)
    melhor = sum(l["ganho"] < l["aleatoria"] for l in linhas)
    pior = sum(l["ganho"] > l["aleatoria"] for l in linhas)
    print(f"   medições até concluir (média; mín. 1, máx. {RETIRADAS}): ganho {g:.2f} | "
          f"aleatória {a:.2f} | topo-base {t:.2f}")
    print(f"   conclui na 1ª medição: ganho {fmt(wilson(g1, n))} | aleatória {100 * a1 / n:.1f}% "
          f"(esperado) | topo-base {fmt(wilson(t1, n))}")
    print(f"   ganho × aleatória, perfil a perfil: melhor em {melhor}, pior em {pior}, "
          f"igual em {n - melhor - pior}")
    print(f"   contenção depois de cada retirada e medição: "
          f"{sum(l['contencao'] for l in linhas)}/{n}; desfechos simulados fora do "
          f"alcançável: {sum(l['violacoes'] for l in linhas)}")
    return {"n": n, "ganho": g, "aleatoria": a, "topo_base": t, "ganho_1": g1,
            "topo_1": t1, "melhor": melhor, "pior": pior}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bdsolos", type=int, default=0,
                    help="avaliar também N perfis conclusivos do acervo nacional")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    print("Próxima medição do Avaliador Parcial — três unidades retiradas de perfis conclusivos")
    rng = random.Random(SEMENTE)
    curado = []
    for f in sorted(PYKKA7.rglob("*.json")):
        if f.name.endswith("_all.json"):
            continue
        for p in carregar_json(f):
            c = caso(p, rng)
            if c:
                curado.append(c)
    saida = {"curado": relatorio("Conjunto curado", curado)}
    if args.bdsolos:
        from .avaliacao_bdsolos import carregar
        dados = [p for _, p in carregar() if classificar(p).conclusivo]
        rng2 = random.Random(SEMENTE)
        rng2.shuffle(dados)
        bd = []
        for p in dados:
            if len(bd) >= args.bdsolos:
                break
            c = caso(p, rng2, lev=p.id_ponto.split("|")[1])
            if c:
                bd.append(c)
        saida["bdsolos"] = relatorio("Acervo nacional (amostra)", bd)
        curado += bd
    if args.json:
        args.json.write_text(json.dumps({"resumo": saida, "casos": curado}, ensure_ascii=False,
                                        indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
