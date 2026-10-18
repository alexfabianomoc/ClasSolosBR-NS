"""Acerto@k do explicador sobre casos reais — fichas originais transcritas.

    python -m nucleo.avaliacao_explicador_real [--json SAIDA.json]

Protocolo (monografia, §3.4):

* **insumo** — os atributos da ficha **original** de cada perfil curado,
  transcritos por `transcricao/originais.py`;
* **alvo** — a classe da ficha **atualizada** (5ª edição, a da base de
  regras), decisão do usuário de 2026-10-12, **até o 4º nível** (decisão
  "saída C");
* **divergência** — o primeiro nível em que o rótulo atualizado fica fora do
  conjunto alcançável, descendo só enquanto o nível de cima concluiu o
  próprio rótulo (§4.3.1). Uma hipótese de nível k só vale se o perfil
  alterado ainda concluir os rótulos dos níveis acima de k;
* **padrão-ouro** — os atributos que a curadoria alterou: valor corrigido
  ou valor **omitido** (`RN_014`: o CaCO3 de 450 g/kg da ficha some do JSON,
  e o grande grupo passa de Carbonático a Ta Eutrófico). Os acréscimos
  ficam de fora, porque em sua maioria são convenção dos curadores (Ca e Mg
  separados de uma soma, 0 em granulometria não determinada). A hipótese acerta quando altera um deles:
  **amplo** pelo nome do atributo (como na §3.4), **por horizonte** quando
  também acerta o horizonte. A versão **estrita** da §3.4 — só os atributos
  que o registro de curadoria descreve como erro corrigido — exige a
  classificação manual do registro e **não é calculada aqui**;
* **denominador** — divergências com exatamente um atributo corrigido.
  As de mais de um atributo são registradas à parte (§3.4). As sem atributo
  corrigido (só símbolo, só acréscimo) estão fora do alcance de hipóteses
  de atributo e são contadas, não avaliadas;
* **pesos** — os adotados, (1; 1; 1), conferidos, para cada perfil, entre os
  melhores da calibração sobre os erros injetados **dos outros perfis** (a
  calibração não vê caso real, mitigação 5; ver
  `avaliacao_explicador.PESOS_ADOTADOS`); Sentinela ajustado sem a partição
  do perfil, como em `avaliacao_explicador`.
  🚨 I-3 da auditoria (2026-10-17): até aqui a calibração usava **todos** os
  injetados, inclusive os do próprio perfil — e entre os do `PE_007` está a
  réplica sintética do seu erro real (Mg do Bt × 10). Com os pesos adotados
  no empate, o efeito era nulo; a separação fica agora correta por
  construção.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .avaliacao_explicador import (PESOS_ADOTADOS, calibrar, carregar_perfis,
                                   detectores, empatados, particoes, posicao)
from .chave5 import CHAVE_5ED
from .estatistica import fmt, wilson
from .explicador import ATRIBUTOS_ANALITICOS, ATRIBUTOS_COR, alterar, explicar
from .injecao import gerar
from .niveis5 import GRANDES_GRUPOS, SUBORDENS, classificar_niveis, coincide
from .niveis5_subgrupos import SUBGRUPOS
from .perfil import carregar_json

ORIGINAIS = Path(__file__).resolve().parents[1] / "transcricao" / "originais"
#: Classificação manual do registro de curadoria (D-2 da auditoria de
#: 2026-10-17): os atributos corrigidos que a nota descreve como erro.
ERROS_DESCRITOS = Path(__file__).parent / "dados" / "curadoria_erros_descritos.json"
ALTERAVEIS = set(ATRIBUTOS_ANALITICOS + ATRIBUTOS_COR)
CLASSES = {r.classe for r in CHAVE_5ED}


def _alcancavel(r):
    return set(r.alcancaveis) | ({r.classe} if r.classe else set())


def _nivel_divergente(rotulo, res):
    """(nível da divergência ou None, desfecho)."""
    for k in range(4):
        r, esperado = res[k], rotulo[k]
        if not esperado:
            return None, f"sem rótulo no nível {k + 1}"
        if r is None:
            return None, f"nível {k + 1} não avaliado"
        if not any(coincide(esperado, c) for c in _alcancavel(r)):
            return k + 1, f"diverge no nível {k + 1}"
        if not (r.conclusivo and coincide(esperado, r.classe)):
            return None, f"não conclui no nível {k + 1}"
    return None, "concorda até o 4º nível"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    curados = carregar_perfis()
    dobra = particoes(curados)
    dets = detectores(curados, dobra)

    # Pesos calibrados em todos os erros injetados (nenhum caso real).
    casos_inj = []
    for inj in gerar(curados).injecoes:
        det = dets[dobra[inj.original.id_ponto]]
        e = explicar(inj.perfil, inj.classe, sentinela=det.escore)
        casos_inj.append({"perfil": inj.original.id_ponto,
                          "hipoteses": e.hipoteses if e else [],
                          "alvo": (lambda h, i=inj: h.indice == i.indice
                                   and h.atributo == i.atributo)})
    empate = empatados(casos_inj, excluir="")
    pesos_de = {}

    def pesos_para(pid):
        if pid not in pesos_de:
            pesos_de[pid] = calibrar(casos_inj, excluir=pid)
        return pesos_de[pid]

    descritos = {pid: {tuple(x) for x in v["erro"]} for pid, v in
                 json.loads(ERROS_DESCRITOS.read_text(encoding="utf-8"))["perfis"].items()}
    linhas = []
    for caminho in sorted(ORIGINAIS.glob("*.json")):
        bruto = json.loads(caminho.read_text(encoding="utf-8"))["items"][0]
        perfil = carregar_json(caminho)[0]
        rotulo = [bruto.get(c) for c in ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")]
        if (rotulo[0] or "").upper() not in CLASSES:
            # `RN_007`: os curadores registraram "unknown" (lacuna da norma);
            # não há classe-alvo a alcançar.
            continue
        alteracoes = bruto.get("_ALTERACOES", [])
        corrigidos = {(a["horizonte"], a["campo"]) for a in alteracoes
                      if a["natureza"] in ("valor corrigido", "omitido na curadoria")
                      and a["campo"] in ALTERAVEIS}
        simbolos = sum(1 for a in alteracoes if a["campo"] == "SIMB_HORIZ")
        res = classificar_niveis(perfil)
        nivel, desfecho = _nivel_divergente(rotulo, res)
        linha = {"id": perfil.id_ponto, "rotulo": rotulo, "nivel": nivel,
                 "desfecho": desfecho, "divergente": nivel is not None,
                 "derivada": [x.classe if x else None for x in res],
                 "corrigidos": sorted(corrigidos), "simbolos_trocados": simbolos,
                 "ficha_atualizada": bruto.get("_TEM_FICHA_ATUALIZADA")}
        if nivel:
            chave = (CHAVE_5ED if nivel == 1 else SUBORDENS[res[0].classe]
                     if nivel == 2 else GRANDES_GRUPOS[(res[0].classe, res[1].classe)]
                     if nivel == 3 else
                     SUBGRUPOS[(res[0].classe, res[1].classe, res[2].classe)])
            alvo = next((rg.classe for rg in chave
                         if coincide(rotulo[nivel - 1], rg.classe)), None)
            linha["alvo"] = alvo
            hip = []
            if alvo is None:
                linha["origem"] = "rótulo sem classe na base desta edição"
            else:
                det = dets[dobra.get(perfil.id_ponto, 0)]
                exp = explicar(perfil, alvo, chave=chave, sentinela=det.escore)
                linha["origem"] = exp.origem if exp else None
                # A hipótese de nível k só vale se preserva os níveis de cima.
                for h in (exp.hipoteses if exp else []):
                    rr = classificar_niveis(alterar(perfil, h.indice, h.atributo,
                                                    h.valor_proposto))
                    if all(rr[j] is not None and rr[j].conclusivo
                           and coincide(rotulo[j], rr[j].classe)
                           for j in range(nivel - 1)):
                        hip.append(h)
            linha["n_hipoteses"] = len(hip)
            nomes = {c for _, c in corrigidos}
            pesos = pesos_para(perfil.id_ponto)
            linha["pesos"] = list(pesos)
            linha["pos_amplo"] = posicao(hip, pesos, lambda h: h.atributo in nomes)
            linha["pos_horizonte"] = posicao(
                hip, pesos, lambda h: (h.indice, h.atributo) in corrigidos)
            erro = descritos.get(perfil.id_ponto, set())
            linha["descritos_como_erro"] = sorted(erro)
            linha["pos_estrito"] = (posicao(hip, pesos,
                                            lambda h: (h.indice, h.atributo) in erro)
                                    if erro else None)
            linha["hipoteses"] = [(h.atributo, h.horizonte, h.valor_informado,
                                   round(h.valor_proposto, 3)) for h in hip[:5]]
        linhas.append(linha)

    div = [l for l in linhas if l["divergente"]]
    print("Explicador sobre casos reais — ficha original × classe da ficha atualizada")
    print("=" * 78)
    print(f"perfis transcritos com ordem válida: {len(linhas)}; com ficha atualizada: "
          f"{sum(1 for l in linhas if l['ficha_atualizada'])}")
    usados = Counter(tuple(v) for v in pesos_de.values())
    print(f"pesos (α, β, γ) usados, calibrados sem o próprio perfil: {dict(usados)}; "
          f"no conjunto inteiro, {len(empate)} combinações empatadas no topo em "
          f"{len(casos_inj)} erros injetados; adotados {PESOS_ADOTADOS} "
          f"{'entre elas' if PESOS_ADOTADOS in empate else 'FORA delas'}")
    print(f"desfechos: {dict(Counter(l['desfecho'] for l in linhas))}")
    saida = {"pesos": {k: list(v) for k, v in pesos_de.items()}, "perfis": len(linhas),
             "desfechos": dict(Counter(l["desfecho"] for l in linhas)), "casos": linhas}
    for nivel in (1, 2, 3, 4, None):
        grupo_n = [l for l in div if nivel is None or l["nivel"] == nivel]
        if not grupo_n:
            continue
        titulo = f"nível {nivel}" if nivel else "todos os níveis"
        um = [l for l in grupo_n if len(l["corrigidos"]) == 1]
        varios = [l for l in grupo_n if len(l["corrigidos"]) > 1]
        nenhum = [l for l in grupo_n if not l["corrigidos"]]
        print(f"\n{titulo}: {len(grupo_n)} divergentes — um atributo corrigido {len(um)},"
              f" vários {len(varios)}, nenhum {len(nenhum)}"
              f" ({sum(1 for l in nenhum if l['simbolos_trocados'])} com símbolo trocado)")
        saida[f"{titulo}|contagem"] = [len(grupo_n), len(um), len(varios), len(nenhum)]
        for rotulo_g, grupo in (("um atributo", um), ("mais de um atributo", varios)):
            n = len(grupo)
            if not n:
                continue
            for chave_pos, nome in (("pos_amplo", "amplo"), ("pos_horizonte", "por horizonte"),
                                    ("pos_estrito", "estrito")):
                base = ([l for l in grupo if l.get("descritos_como_erro")]
                        if nome == "estrito" else grupo)
                n = len(base)
                if not n:
                    print(f"   {rotulo_g:<20} {nome:<14} nenhum caso com erro descrito no registro")
                    continue
                partes = []
                for k in (1, 3, 5):
                    a = sum(1 for l in base if l.get(chave_pos) is not None and l[chave_pos] <= k)
                    partes.append(f"@{k} {a}/{n} {fmt(wilson(a, n))}")
                    saida[f"{titulo}|{rotulo_g}|{nome}|@{k}"] = [a, n]
                print(f"   {rotulo_g:<20} {nome:<14} " + "  ".join(partes))
    print("\ncasos divergentes:")
    for l in div:
        k = l["nivel"]
        print(f"  {l['id']:<36} nível {k} rótulo {l['rotulo'][k - 1]!s:<18}"
              f" deriva {l['derivada'][k - 1]!s:<16} origem {l.get('origem')}"
              f" corrigidos {l['corrigidos']} pos {l.get('pos_amplo')} hip {l.get('hipoteses')}")
    todos = json.loads(ERROS_DESCRITOS.read_text(encoding="utf-8"))["perfis"]
    com_erro = sum(1 for v in todos.values() if v["erro"])
    outra = sum(1 for v in todos.values() if v["outra"])
    print(f"\nRegistro de curadoria (classificação manual, {ERROS_DESCRITOS.name}): "
          f"dos {len(todos)} perfis com atributo alterável corrigido, a nota descreve "
          f"a correção como erro em {com_erro}, com outra natureza em {outra}, e não a "
          f"menciona nos demais.")
    saida["registro"] = {"perfis": len(todos), "erro": com_erro, "outra": outra}
    if args.json:
        args.json.write_text(json.dumps(saida, ensure_ascii=False, indent=1,
                                        default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
