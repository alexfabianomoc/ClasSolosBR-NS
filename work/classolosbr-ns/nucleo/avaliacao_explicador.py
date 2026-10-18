"""Avaliação do Explicador e do Sentinela sobre erros injetados.

    python -m nucleo.avaliacao_explicador [--json SAIDA.json]

Protocolo (monografia, §3.4 e §3.5):

1. **Injeção** (`nucleo/injecao.py`): deslocamento do separador decimal (×10 e
   ÷10) sobre os atributos analíticos dos perfis do conjunto curado cuja
   classificação é conclusiva; retêm-se só as injeções que tornam a classe do
   perfil limpo inalcançável. A classe-alvo do explicador é a do perfil
   limpo, e não o rótulo da ficha.
2. **Sentinela**: detector ajustado em validação cruzada estratificada em
   cinco partições (estratos = ordem registrada). O escore de um perfil vem
   sempre do detector ajustado **sem** a partição dele.
3. **Pesos (α, β, γ)**: calibrados só sobre erros injetados e avaliados sobre
   injeções distintas — aqui, por deixar-um-perfil-de-fora: para cada perfil,
   os pesos são escolhidos nas injeções dos **outros** perfis e aplicados às
   dele. Com poucos perfis injetados, uma partição fixa em metades deixaria
   cada lado com três ou quatro perfis.
4. **Acerto@k** (k = 1, 3, 5): a hipótese correta altera o atributo injetado
   no horizonte injetado. Intervalo de Wilson (95%) e reamostragem por perfil
   (mitigação 11).

⚠️ Os números medem o explicador sobre **erro sintético**; a §3.5 adverte
que ele é mais nítido que o real e pode superestimar o desempenho. Não se
agregam a casos reais, que dependem da transcrição das fichas originais.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import horizontes  # noqa: F401  (coloca dags/ no sys.path)
from .avaliacao import PYKKA7
from .avaliador import classificar
from .estatistica import auc, bootstrap_por_grupo, fmt, wilson
from .explicador import ATRIBUTOS_ANALITICOS, explicar
from .injecao import FATORES, gerar
from .perfil import carregar_json

from sentinela.anomalia import DetectorAnomalia  # noqa: E402

GRADE = (0.0, 0.5, 1.0, 2.0)

#: Pesos (α, β, γ) adotados — decisão do usuário de 2026-10-17. A calibração
#: em grade sobre os erros injetados **não identifica um ponto**: 20 das 63
#: combinações empatam em (Acerto@1, Acerto@3, MRR) no conjunto todo — as de
#: α/β entre 1 e 2, com γ qualquer —, e o empate se repete, com 20 a 23
#: combinações, em cada partição deixar-um-perfil-de-fora. O "(0,5; 0,5; 0)"
#: relatado até então era só o primeiro do empate
#: na ordem de `itertools.product`. Adotam-se os uniformes, que pertencem ao
#: empate e preservam a tipicidade para os casos reais (monografia, §4.3.2).
PESOS_ADOTADOS = (1.0, 1.0, 1.0)
PARTICOES = 5
SEMENTE = 20261015


def carregar_perfis():
    arquivos = [a for a in sorted(PYKKA7.rglob("*.json"))
                if not a.name.endswith("_all.json")]
    return [p for a in arquivos for p in carregar_json(a)]


def particoes(perfis, k=PARTICOES, semente=SEMENTE) -> dict[str, int]:
    """Partição estratificada pela ordem registrada (round-robin por estrato)."""
    rng = random.Random(semente)
    por_estrato = defaultdict(list)
    for p in perfis:
        por_estrato[p.classe_registrada[0] or "?"].append(p.id_ponto)
    dobra, i = {}, 0
    for estrato in sorted(por_estrato):
        ids = sorted(por_estrato[estrato])
        rng.shuffle(ids)
        for pid in ids:
            dobra[pid] = i % k
            i += 1
    return dobra


def detectores(perfis, dobra) -> dict[int, DetectorAnomalia]:
    return {d: DetectorAnomalia().ajustar([p for p in perfis if dobra[p.id_ponto] != d])
            for d in range(PARTICOES)}


def posicao(hipoteses, pesos, alvo) -> int | None:
    """Posição (1-based) da hipótese-alvo na ordem dada pelos pesos."""
    a, b, g = pesos
    ordem = sorted(hipoteses, key=lambda h: (
        -(a * h.componentes["sigma"] + b * h.componentes["magnitude"]
          + g * h.componentes["tau"]),
        h.delta_relativo, h.atributo, h.indice))
    for pos, h in enumerate(ordem, 1):
        if alvo(h):
            return pos
    return None


def acerto(posicoes, k) -> int:
    return sum(1 for p in posicoes if p is not None and p <= k)


def empatados(casos, excluir: str) -> list[tuple[float, float, float]]:
    """Combinações da grade que maximizam (Acerto@1, Acerto@3, MRR) nos casos
    dos outros perfis — todas, e não só a primeira (ver `PESOS_ADOTADOS`)."""
    treino = [c for c in casos if c["perfil"] != excluir]
    melhores, chave_melhor = [], None
    for pesos in itertools.product(GRADE, repeat=3):
        if pesos == (0.0, 0.0, 0.0):
            continue
        pos = [posicao(c["hipoteses"], pesos, c["alvo"]) for c in treino]
        mrr = round(sum(1 / p for p in pos if p) / max(1, len(pos)), 12)
        chave = (acerto(pos, 1), acerto(pos, 3), mrr)
        if chave_melhor is None or chave > chave_melhor:
            melhores, chave_melhor = [pesos], chave
        elif chave == chave_melhor:
            melhores.append(pesos)
    return melhores


def calibrar(casos, excluir: str):
    """Os pesos adotados, se estão entre os melhores da grade; senão, o
    primeiro dos melhores — e então a adoção precisa ser revista."""
    melhores = empatados(casos, excluir)
    return PESOS_ADOTADOS if PESOS_ADOTADOS in melhores else melhores[0]


def main(argv=None) -> int:
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--json", type=Path, default=None)
    args = ap_.parse_args(argv)

    if not PYKKA7.exists():
        print(f"conjunto curado não encontrado em {PYKKA7}", file=sys.stderr)
        return 2
    perfis = carregar_perfis()
    dobra = particoes(perfis)
    dets = detectores(perfis, dobra)
    saida: dict = {"perfis": len(perfis)}

    # ---------------------------------------------------- 1. injeção -------
    apur = gerar(perfis)
    injs = apur.injecoes
    print("Avaliação do Explicador sobre erros injetados (separador decimal)")
    print("=" * 72)
    print(f"perfis no conjunto curado:           {len(perfis)}")
    print(f"perfis conclusivos (elegíveis):      {apur.perfis_elegiveis}")
    tentativas = sum(apur.desfechos.values())
    print(f"injeções tentadas:                   {tentativas}")
    for k_, v in apur.desfechos.items():
        print(f"   {k_:<20} {v:>6}  ({fmt(v / tentativas)})")
    por_perfil = Counter(i.original.id_ponto for i in injs)
    print(f"injeções retidas (divergência):      {len(injs)} em {len(por_perfil)} perfis")
    print(f"   por atributo: {dict(Counter(i.atributo for i in injs).most_common())}")
    print(f"   por tipo:     {dict(Counter(i.tipo for i in injs))}")
    saida["injecao"] = {
        "elegiveis": apur.perfis_elegiveis, "tentativas": tentativas,
        "desfechos": apur.desfechos, "retidas": len(injs),
        "perfis_com_injecao": len(por_perfil),
        "por_atributo": dict(Counter(i.atributo for i in injs)),
        "por_tipo": dict(Counter(i.tipo for i in injs)),
    }

    # ------------------------------------------------- 2. explicação -------
    casos = []
    for inj in injs:
        det = dets[dobra[inj.original.id_ponto]]
        exp = explicar(inj.perfil, inj.classe, sentinela=det.escore)
        alvo_estrito = (lambda h, i=inj: h.indice == i.indice and h.atributo == i.atributo)
        alvo_amplo = (lambda h, i=inj: h.atributo == i.atributo)
        casos.append({"perfil": inj.original.id_ponto, "inj": inj, "exp": exp,
                      "hipoteses": exp.hipoteses if exp else [],
                      "alvo": alvo_estrito, "alvo_amplo": alvo_amplo})

    sem_exp = sum(1 for c in casos if c["exp"] is None)
    origens = Counter(c["exp"].origem for c in casos if c["exp"])
    tamanhos = [len(c["hipoteses"]) for c in casos]
    contem = sum(1 for c in casos if any(c["alvo"](h) for h in c["hipoteses"]))
    print()
    print(f"origem da refutação: {dict(sorted(origens.items()))}"
          f"  (1 = condição falsa; 2 = classe precedente concluída)")
    print(f"hipóteses por caso: média {sum(tamanhos) / max(1, len(tamanhos)):.1f},"
          f" mín {min(tamanhos, default=0)}, máx {max(tamanhos, default=0)}")
    print(f"hipótese correta presente na lista:  {contem}/{len(casos)}  "
          f"{fmt(wilson(contem, len(casos)))}")
    saida["explicacao"] = {"sem_explicacao": sem_exp, "origens": dict(origens),
                           "hipoteses_media": sum(tamanhos) / max(1, len(tamanhos)),
                           "hipoteses_min": min(tamanhos, default=0),
                           "hipoteses_max": max(tamanhos, default=0),
                           "correta_na_lista": contem}

    # ------------------------------------------- 3. calibração e Acerto@k --
    empates = {pid: empatados(casos, pid) for pid in por_perfil}
    pesos_por_perfil = {pid: (PESOS_ADOTADOS if PESOS_ADOTADOS in emp else emp[0])
                        for pid, emp in empates.items()}
    pos_cal = [posicao(c["hipoteses"], pesos_por_perfil[c["perfil"]], c["alvo"])
               for c in casos]
    pos_cal_amplo = [posicao(c["hipoteses"], pesos_por_perfil[c["perfil"]],
                             c["alvo_amplo"]) for c in casos]

    variantes = {
        "calibrado (adotados, deixar-um-perfil-de-fora)": pos_cal,
        "uniforme (1, 1, 1)": [posicao(c["hipoteses"], (1, 1, 1), c["alvo"]) for c in casos],
        "só σ (Sentinela)": [posicao(c["hipoteses"], (1, 0, 0), c["alvo"]) for c in casos],
        "só magnitude": [posicao(c["hipoteses"], (0, 1, 0), c["alvo"]) for c in casos],
        "só τ (tipicidade)": [posicao(c["hipoteses"], (0, 0, 1), c["alvo"]) for c in casos],
    }
    n = len(casos)
    print()
    print(f"Acerto@k — {n} casos injetados, {len(por_perfil)} perfis;"
          f" IC 95% de Wilson; [reamostragem por perfil]")
    print("-" * 72)
    saida["acerto"] = {}
    for nome, pos in variantes.items():
        linha = f"{nome:<38}"
        saida["acerto"][nome] = {}
        for k in (1, 3, 5):
            a = acerto(pos, k)
            grupos = defaultdict(list)
            for c, p in zip(casos, pos):
                grupos[c["perfil"]].append(1 if p is not None and p <= k else 0)
            lo_b, hi_b = bootstrap_por_grupo(list(grupos.values()))
            w = wilson(a, n)
            linha += f"  @{k} {a}/{n} {fmt(w)}"
            saida["acerto"][nome][f"@{k}"] = {
                "acertos": a, "n": n, "p": w[0], "wilson": [w[1], w[2]],
                "bootstrap_perfil": [lo_b, hi_b]}
        print(linha)
        print(f"{'':<38}  reamostragem por perfil: " + "  ".join(
            f"@{k} [{fmt(v['bootstrap_perfil'][0])}–{fmt(v['bootstrap_perfil'][1])}]"
            for k, v in ((int(c[1:]), saida["acerto"][nome][c]) for c in ("@1", "@3", "@5"))))
    aleat = {k: sum(min(k, len(c["hipoteses"])) / len(c["hipoteses"])
                    for c in casos if any(c["alvo"](h) for h in c["hipoteses"])) / max(1, n)
             for k in (1, 3, 5)}
    print(f"{'ordem aleatória (esperado)':<38}"
          + "".join(f"  @{k} {fmt(aleat[k])}" for k in (1, 3, 5)))
    saida["acerto"]["ordem aleatória (esperado)"] = aleat
    a1_amplo = acerto(pos_cal_amplo, 1)
    print(f"calibrado, alvo só pelo atributo:       @1 {a1_amplo}/{n} "
          f"{fmt(wilson(a1_amplo, n))}")
    saida["acerto_atributo_calibrado_@1"] = a1_amplo
    escolhidos = Counter(pesos_por_perfil.values())
    razoes = sorted({round(a / b, 3) for emp in empates.values() for a, b, _ in emp if b})
    gamas = sorted({g for emp in empates.values() for _, _, g in emp})
    print(f"combinações empatadas no topo, por perfil: "
          f"{dict(Counter(len(e) for e in empates.values()))} (de {len(GRADE) ** 3 - 1});"
          f" α/β nos empates: {razoes}; γ nos empates: {gamas}")
    print(f"pesos adotados {PESOS_ADOTADOS} entre os empatados em "
          f"{sum(PESOS_ADOTADOS in e for e in empates.values())}/{len(empates)} perfis;"
          f" usados: {dict(escolhidos)}")
    saida["pesos_por_perfil"] = {k: list(v) for k, v in pesos_por_perfil.items()}
    saida["empates_por_perfil"] = {k: [list(p) for p in v] for k, v in empates.items()}

    # ---------------------------------------------- 4. detecção (σ) --------
    positivos, negativos = [], []
    for p in perfis:
        det = dets[dobra[p.id_ponto]]
        for h in p.horizontes:
            for a in ATRIBUTOS_ANALITICOS:
                v = h.get(a)
                if isinstance(v, bool) or not isinstance(v, (int, float)) or v == 0:
                    continue
                negativos.append(det.escore_valor(h.simbolo, a, float(v)))
                for fator, _ in FATORES:
                    positivos.append(det.escore_valor(h.simbolo, a, float(v) * fator))
    area = auc(positivos, negativos)
    vp = sum(1 for x in positivos if x >= 0.5)
    fp = sum(1 for x in negativos if x >= 0.5)
    print()
    print("Sentinela — detecção do valor injetado (todas as injeções tentadas,"
          " não só as que divergem)")
    print("-" * 72)
    print(f"valores limpos: {len(negativos)}; valores injetados: {len(positivos)}")
    print(f"AUC: {area:.3f}")
    print(f"limiar σ ≥ 0,5 (três MADs): revocação {vp}/{len(positivos)} "
          f"{fmt(wilson(vp, len(positivos)))}; falso alarme {fp}/{len(negativos)} "
          f"{fmt(wilson(fp, len(negativos)))}")
    print("   (precisão não é reportada: a razão 2:1 entre injetados e limpos é")
    print("    artefato do protocolo, não a prevalência de erro no acervo)")
    saida["sentinela"] = {"limpos": len(negativos), "injetados": len(positivos),
                          "auc": area, "vp": vp, "fp": fp}

    print()
    print("Leitura. Erro sintético, mais nítido que o real (§3.5). O Acerto@k")
    print("sobre casos reais depende da transcrição das fichas originais e não")
    print("é agregado a este.")
    if args.json:
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
