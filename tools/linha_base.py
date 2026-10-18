#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linha de base: SmartSolos Expert (/verification) nos dois conjuntos de avaliação.

    python tools/linha_base.py coletar   # chama a API e grava o cache (retoma de onde parou)
    python tools/linha_base.py apurar    # apura L0–L4 e compara com o núcleo (sem rede)

Conjuntos — os mesmos do núcleo (monografia, §3.2):
* curado: os 94 perfis do PYKKA7;
* acervo nacional: perfis do BDSolos corroborados, sem os registros que
  repetem o conjunto curado, com rótulo ao menos no 1º nível (5.808).

Concordância por nível n: entre os perfis com rótulo até o nível n, a
proporção cuja faixa L (nível mais profundo em que inferido e registrado
coincidem, contados de cima) é ≥ n. A faixa é recalculada aqui, perfil a
perfil, contra o rótulo enviado, com nomes normalizados (sem acento, caixa e
espaços); "unknown" nunca conta como concordância. O par que a API devolve
(`items_bd`) não serve de referência: ela preenche com "unknown" os níveis
que o rótulo não tem, e "unknown" inferido casaria com eles.

Credenciais: ~/.agroapi.json (consumer_key, consumer_secret), nunca impressas.
"""
from __future__ import annotations

import json
import os
import sys
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import agroapi_verify as A  # noqa: E402
import bdsolos_adapter as B  # noqa: E402

CACHE = RAIZ / "work" / "classolosbr-ns" / "resultados" / "linha_base_cache.json"
LOTE = 50
CAMPOS = ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")


def norm(x):
    t = unicodedata.normalize("NFD", str(x or "")).encode("ascii", "ignore").decode()
    return " ".join(t.upper().split())


def conjuntos():
    curado, _ = A.carregar_pykka7()
    bd, _ = B.ler_perfis()
    bd = B.filtrar(bd, nivel_minimo=1, corroborado=True, sem_curado=True)
    return {"curado": curado, "bdsolos": bd}


def credencial():
    c = json.load(open(os.path.expanduser("~/.agroapi.json"), encoding="utf-8"))
    return A.Credencial(None, c["consumer_key"], c["consumer_secret"], A.URL_TOKEN, 60, False)


def _carrega_cache():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {"respostas": {}, "falhas": {}}


def _grava_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE)


def _envia(cred, perfis):
    carga = {"items": [A.limpar(p) for p in perfis]}
    codigo, resp = A.chamar("/verification", cred, carga, timeout=180)
    if codigo == 200 and isinstance(resp, dict) and resp.get("items"):
        inf = {i["ID_PONTO"]: i for i in resp["items"]}
        bd = {i["ID_PONTO"]: i for i in resp.get("items_bd", [])}
        return {pid: {"inferido": inf.get(pid), "registrado": bd.get(pid)} for pid in inf}, None
    return None, f"HTTP {codigo}: {str(resp)[:300]}"


def coletar():
    cache = _carrega_cache()
    cred = credencial()
    for nome, perfis in conjuntos().items():
        faltam = [p for p in perfis if f"{nome}|{p['ID_PONTO']}" not in cache["respostas"]]
        print(f"{nome}: {len(perfis)} perfis; já no cache {len(perfis) - len(faltam)}; a enviar {len(faltam)}")
        for i in range(0, len(faltam), LOTE):
            lote = faltam[i:i + LOTE]
            ok, erro = _envia(cred, lote)
            if ok is None:
                time.sleep(5)
                ok, erro = _envia(cred, lote)
            if ok is None:                         # lote recusado: perfil a perfil
                ok = {}
                for p in lote:
                    r, e = _envia(cred, [p])
                    if r:
                        ok.update(r)
                    else:
                        cache["falhas"][f"{nome}|{p['ID_PONTO']}"] = e
            for pid, r in ok.items():
                cache["respostas"][f"{nome}|{pid}"] = r
                cache["falhas"].pop(f"{nome}|{pid}", None)
            _grava_cache(cache)
            print(f"   {nome}: {min(i + LOTE, len(faltam))}/{len(faltam)}"
                  f" (respostas {len(cache['respostas'])}, falhas {len(cache['falhas'])})", flush=True)
    print("coleta concluída")


def faixa(inferido, registrado):
    n = 0
    for k, campo in enumerate(CAMPOS, start=1):
        a, b = norm((inferido or {}).get(campo)), norm((registrado or {}).get(campo))
        # "unknown" nunca é concordância: a API preenche com ele os níveis
        # que o rótulo enviado não tem, e o sistema o devolve quando não conclui.
        if a and a == b and a != "UNKNOWN":
            n = k
        else:
            break
    return n


def _wilson(k, n):
    sys.path.insert(0, str(RAIZ / "work" / "classolosbr-ns"))
    from nucleo.estatistica import fmt, wilson
    return f"{k}/{n} {fmt(wilson(k, n))}" if n else "—"


def _boot(linhas, ok, reps=1000, semente=20261017):
    """Intervalo por reamostragem de levantamentos (acervo nacional)."""
    import random
    from collections import defaultdict
    por = defaultdict(list)
    for l in linhas:
        por[l["lev"]].append(1 if ok(l) else 0)
    chaves, rng, vals = list(por), random.Random(semente), []
    for _ in range(reps):
        amostra = [x for g in (rng.choice(chaves) for _ in chaves) for x in por[g]]
        vals.append(sum(amostra) / len(amostra))
    vals.sort()
    lo, hi = (f"{100 * v:.1f}".replace(".", ",") for v in (vals[int(.025 * reps)], vals[int(.975 * reps) - 1]))
    return f"[lev.: {lo}%–{hi}%]"


def apurar():
    sys.path.insert(0, str(RAIZ / "work" / "classolosbr-ns"))
    from collections import Counter
    from nucleo.avaliador import classificar
    from nucleo.chave5 import CHAVE_5ED
    from nucleo.perfil import _aplicar_profundidade_observada, de_dicionario
    from nucleo.avaliacao import _recorte
    recorte = _recorte(CHAVE_5ED)
    cache = _carrega_cache()
    saida = {}
    for nome, perfis in conjuntos().items():
        linhas = []
        for p in perfis:
            r = cache["respostas"].get(f"{nome}|{p['ID_PONTO']}")
            if not r:
                continue
            inf, reg = r["inferido"] or {}, r["registrado"] or {}
            rot = {c: p.get(c) for c in CAMPOS}
            nivel_rot = B.nivel_do_rotulo(rot)
            perfil = de_dicionario(p)
            if nome == "curado":
                # Como `carregar_json`: profundidade observada dos horizontes
                # abertos, lida nas fichas (11º defeito). Sem ela, o núcleo
                # concluía 3 perfis a menos que na avaliação oficial.
                _aplicar_profundidade_observada(perfil)
            nuc = classificar(perfil, CHAVE_5ED)
            alc = set(nuc.alcancaveis) | ({nuc.classe} if nuc.classe else set())
            conclusivo = bool(nuc.classe) and not nuc.alcancaveis
            sr_ordem = norm(inf.get("ORDEM"))
            linhas.append({
                "id": p["ID_PONTO"], "lev": str(p["ID_PONTO"]).split("|")[1] if nome == "bdsolos" else p["ID_PONTO"],
                "faixa": faixa(inf, reg), "faixa_rotulo": faixa(inf, rot), "nivel_rot": nivel_rot,
                "rotulo_ordem": norm(rot["ORDEM"]), "sr_ordem": sr_ordem,
                "sr_desconhecido": sr_ordem in ("", "UNKNOWN", "DESCONHECIDO"),
                "nuc_classe": norm(nuc.classe) if conclusivo else None,
                "nuc_alc": {norm(x) for x in alc}, "recorte": norm(rot["ORDEM"]) in {norm(x) for x in recorte},
            })
        falhas = sum(1 for k in cache["falhas"] if k.startswith(nome + "|"))
        print(f"\n=== {nome}: {len(linhas)} perfis com resposta; {falhas} sem resposta")
        incoer = sum(1 for l in linhas if l["faixa"] != l["faixa_rotulo"])
        print(f"   faixa pelo par devolvido pela API × faixa pelo nosso rótulo: {incoer} diferem")
        print("   distribuição das faixas (contra o rótulo enviado):", dict(sorted(Counter(l["faixa_rotulo"] for l in linhas).items())))
        print("   sistema de referência × rótulo — concordância por nível (perfis com rótulo até o nível):")
        res = {}
        for n in (1, 2, 3, 4):
            base = [l for l in linhas if l["nivel_rot"] >= n]
            k = sum(1 for l in base if l["faixa_rotulo"] >= n)
            extra = ("  " + _boot(base, lambda l, n=n: l["faixa_rotulo"] >= n)) if nome == "bdsolos" and base else ""
            print(f"      nível {n}: {_wilson(k, len(base))}{extra}")
            res[n] = {"k": k, "n": len(base)}
        des = [l for l in linhas if l["sr_desconhecido"]]
        print(f"   ordem 'desconhecida' devolvida pelo sistema de referência: {len(des)}")
        if des:
            parcial = sum(1 for l in des if l["nuc_alc"])
            contem = sum(1 for l in des if l["rotulo_ordem"] in l["nuc_alc"])
            print(f"      núcleo devolve resposta parcial (conjunto alcançável não vazio): {_wilson(parcial, len(des))}")
            print(f"      e o conjunto contém a ordem registrada: {_wilson(contem, len(des))}")
        for rot_nome, filtro in (("todos", lambda l: True), ("ordens do recorte", lambda l: l["recorte"]),
                                 ("demais ordens", lambda l: not l["recorte"])):
            sub = [l for l in linhas if filtro(l) and not l["sr_desconhecido"]]
            if not sub:
                continue
            c = Counter()
            for l in sub:
                if l["nuc_classe"] == l["sr_ordem"]:
                    c["núcleo conclui a ordem do SR"] += 1
                elif l["nuc_classe"] is None and l["sr_ordem"] in l["nuc_alc"]:
                    c["núcleo não conclui; ordem do SR alcançável"] += 1
                elif l["nuc_classe"] is not None:
                    c["núcleo conclui outra ordem"] += 1
                else:
                    c["núcleo não conclui; ordem do SR fora do alcançável"] += 1
            print(f"   núcleo × sistema de referência, 1º nível — {rot_nome} ({len(sub)} perfis com ordem do SR):")
            for k_, v in c.most_common():
                print(f"      {k_:<52} {_wilson(v, len(sub))}")
            sr_ok = sum(1 for l in sub if l["sr_ordem"] == l["rotulo_ordem"])
            nuc_ok = sum(1 for l in sub if l["nuc_classe"] == l["rotulo_ordem"])
            print(f"      concordância com o rótulo nesses perfis: SR {_wilson(sr_ok, len(sub))}; núcleo {_wilson(nuc_ok, len(sub))}")
        saida[nome] = {"perfis": len(linhas), "falhas": falhas, "por_nivel": res}
    return saida


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "coletar":
        coletar()
    elif len(sys.argv) > 1 and sys.argv[1] == "apurar":
        apurar()
    else:
        print(__doc__)
