"""Experimento de integração — variantes A0, A, B e C sobre E1–E4.

    python -m integracao.experimento rodar E1 [--limite N]   # grava resultados/etapa1_integracao/E1.jsonl
    python -m integracao.experimento agregar                 # métricas, comparações pareadas, resumo

O pré-registro está em `experimento_integracao/config/experimento.json`
(SHA-256 em `experimento.json.sha256`). Este módulo só o executa.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "dags"))
sys.path.insert(0, str(RAIZ.parents[1] / "tools"))

from nucleo import avaliador as AV  # noqa: E402
from nucleo.estatistica import wilson  # noqa: E402
from nucleo.horizontes import leitura_atual  # noqa: E402
from sentinela import gramatica_sufixos as gs  # noqa: E402

from . import fluxo as FX  # noqa: E402
from .inferidor import assinatura, gatilho  # noqa: E402

EXP = RAIZ / "experimento_integracao"
import os as _os
#: Auditoria v3: a rodada nova grava no diretório próprio (variável de ambiente),
#: sem tocar em resultados/etapa1_integracao (rodada v2).
SAIDA = Path(_os.environ.get("CLASSOLOSBR_SAIDA_EXPERIMENTO", EXP / "resultados" / "etapa1_integracao"))
PYKKA7 = RAIZ.parents[1] / "raw" / "pykka7-smartsolos-dataset"
ORIGINAIS = RAIZ / "transcricao" / "originais"
TIPO_B = set("twihs")
OUTROS_TIPO = set("gfcvm")
SEMENTE_BOOT = 20261019
REPS = 2000


# ------------------------------------------------------------- conjuntos --

def mascara(simbolo: str) -> str | None:
    """'2Bt2' → '2B' quando o símbolo é B com sufixo de tipo de B e sem
    sufixo de outro tipo (g, f, c, v, m), cuja perda o 'B' sem sufixo não
    representa como pendente (decisão de 2026-10-15). Senão None."""
    moderno = leitura_atual(simbolo) or simbolo
    a = gs.analisa(moderno)
    if not a.reconhecido or a.mesclado or a.principal != "B":
        return None
    suf = {s.rstrip(gs.MACRON) for s in a.sufixos}
    if not (suf & TIPO_B) or (suf & OUTROS_TIPO):
        return None
    return f"{a.litologico or ''}B"


def mascarar(item: dict) -> tuple[dict, list[int]] | None:
    hs = item.get("HORIZONTES") or []
    if any(gatilho(h.get("SIMB_HORIZ") or "") for h in hs):
        return None
    m = copy.deepcopy(item)
    ks = []
    for k, h in enumerate(m["HORIZONTES"]):
        novo = mascara(h.get("SIMB_HORIZ") or "")
        if novo:
            h["SIMB_HORIZ"] = novo
            ks.append(k)
    return (m, ks) if ks else None


def apagar_primeiro(item: dict) -> tuple[dict, list[int]] | None:
    hs = item.get("HORIZONTES") or []
    if any(gatilho(h.get("SIMB_HORIZ") or "") for h in hs):
        return None
    for k, h in enumerate(hs):
        if mascara(h.get("SIMB_HORIZ") or ""):
            m = copy.deepcopy(item)
            m["HORIZONTES"][k]["SIMB_HORIZ"] = ""
            return m, [k]
    return None


def _lev(pid: str) -> str:
    partes = str(pid).split("|")
    return partes[1] if len(partes) > 1 else str(pid)


def bdsolos_teste():
    import bdsolos_adapter as B
    part = json.loads((EXP / "modelos" / "particao_levantamentos.json").read_text(encoding="utf-8"))
    teste, treino = set(part["teste"]), set(part["treino"])
    perfis, _ = B.ler_perfis()
    saida = []
    for p in B.filtrar(perfis, sem_curado=True):
        lev = _lev(p.get("ID_PONTO"))
        if lev in teste:
            saida.append((p, lev, "teste"))
        elif lev not in treino:
            saida.append((p, lev, "levantamento sem horizonte rotulável (nunca visto pelos modelos)"))
    return saida


def curados():
    for a in sorted(PYKKA7.rglob("*.json")):
        if a.name.endswith("_all.json"):
            continue
        yield json.JSONDecoder().raw_decode(a.read_text(encoding="utf-8"))[0]["items"][0]


def conjunto(nome: str):
    """Itens (perfil_avaliado, perfil_verdadeiro | None, grupo, horizontes_alterados, origem)."""
    if nome in ("E1", "E2"):
        for p, lev, origem in bdsolos_teste():
            if nome == "E1":
                if origem != "teste":
                    continue
                r = mascarar(p)
                if r:
                    yield r[0], p, lev, r[1], origem
            elif any(gatilho(h.get("SIMB_HORIZ") or "") for h in p.get("HORIZONTES") or []):
                yield p, None, lev, [], origem
    elif nome in ("E3", "E3b"):
        for it in curados():
            r = mascarar(it) if nome == "E3" else apagar_primeiro(it)
            if r:
                yield r[0], it, it["ID_PONTO"], r[1], "curado"
    elif nome == "E4":
        for a in sorted(ORIGINAIS.glob("*.json")):
            it = json.loads(a.read_text(encoding="utf-8"))["items"][0]
            yield it, None, it["ID_PONTO"], [], "ficha original"
    else:
        raise ValueError(nome)


# ---------------------------------------------------------------- registro --

def _alc(r):
    return sorted(set(r.alcancaveis) | ({r.classe} if r.classe else set()))


def _resumo_saida(s: dict) -> dict:
    obs = s["observacional"]
    cond = s.get("condicional", {})
    inf = s.get("inferencia", {})
    props = inf.get("propostas", [])
    cands = [c for p in props for c in p["candidatos"]]
    exp = s.get("explicador", {})
    hip_a = exp.get("hipoteses_de_anotacao")
    hip_n = exp.get("hipoteses_numericas")
    cen = cond.get("cenarios", [])
    topo = next((c["resultado"] for c in cen if c["compativel"]), None)
    return {
        "obs": {"classe": obs["classe"], "conclusivo": obs["conclusivo"], "alc": obs["alcancaveis"]},
        "obs_sha": FX._sha({k: obs[k] for k in ("classe", "conclusivo", "alcancaveis", "pendencias",
                                                "prova_texto")}),
        "versao_sha": FX._sha(s["versao"]),
        "gatilhos": len(s.get("gatilhos", {})),
        "propostas": len(props),
        "abstencoes": [p["abstencao"].split(" (")[0].split(" κ")[0] for p in props if p["abstencao"]],
        "candidatos": len(cands), "candidatos_bem_formados": sum(c["bem_formado"] for c in cands),
        "propostas_topo": [{"horizonte_id": p["horizonte_id"], "anotado": p["simbolo_anotado"],
                            "topo": next((c["simbolo"] for c in p["candidatos"] if c["bem_formado"]), None),
                            "abstencao": p["abstencao"]} for p in props],
        "cenarios": len(cen), "compativeis": sum(c["compativel"] for c in cen),
        "incompativeis": [c["incompatibilidade"] for c in cen if not c["compativel"]],
        "cond": ({"classe": topo["classe"], "conclusivo": topo["conclusivo"], "alc": topo["alcancaveis"]}
                 if topo else None),
        "robusta": cond.get("condicional_robusta"),
        "avaliacao_completa": cond.get("avaliacao_completa"),
        "cenarios_detalhe": [{"cenario": c["cenario"], "compativel": c["compativel"],
                              "classe": c["resultado"]["classe"], "conclusivo": c["resultado"]["conclusivo"],
                              "alc": c["resultado"]["alcancaveis"],
                              "simbolos": [x["simbolo_inferido"] for x in c["substituicoes"]]} for c in cen],
        "propostas_detalhe": [{"horizonte_id": p["horizonte_id"], "anotado": p["simbolo_anotado"],
                               "abstencao": p["abstencao"],
                               "candidatos": [{"simbolo": c["simbolo"], "kappa": round(c["kappa"], 4),
                                               "escore": c["escore"], "bem_formado": c["bem_formado"],
                                               "p_tipo": {k: c["p_sufixos"].get(k) for k in "twihsgfcv"}}
                                              for c in p["candidatos"]]} for p in props],
        "violacoes_contencao": cond.get("violacoes_de_contencao") or [],
        "conflitos": [{"h": c["horizonte_id"], "anotado": c["simbolo_anotado"], "sinal": c["sinal"],
                       "cand": [x["simbolo"] for x in c["candidatos"]]}
                      for c in s.get("conflitos_de_anotacao", {}).get("sinalizados", [])],
        "explicador": exp.get("status"),
        "hip_anotacao": hip_a if isinstance(hip_a, list) else [],
        "hip_numericas": ([{k: h[k] for k in ("atributo", "horizonte", "valor_informado",
                                              "valor_proposto")} for h in hip_n]
                          if isinstance(hip_n, list) else None),
        "proxima": s.get("proxima_determinacao", {}).get("candidatas"),
        "verificacoes": s["verificacoes"], "tempo_s": s["tempo_s"],
    }


def rodar(nome: str, limite: int = 0) -> Path:
    SAIDA.mkdir(parents=True, exist_ok=True)
    infs = {"A": None, "B": FX.inferidor_padrao("rede"), "C": FX.inferidor_padrao("arvores")}
    for v, i in infs.items():
        if i is not None and not i.disponivel:
            raise SystemExit(f"modelo da variante {v} indisponível: {i.motivo_indisponivel}")
    caminho = SAIDA / f"{nome}.jsonl"
    numerico = nome == "E4"
    recomendar = nome in ("E3", "E4")   # E3b: desligada por custo (emenda 5)
    n = 0
    t0 = time.time()
    with caminho.open("w", encoding="utf-8") as f:
        for avaliado, verdadeiro, grupo, alterados, origem in conjunto(nome):
            if limite and n >= limite:
                break
            n += 1
            reg = (avaliado.get("ORDEM") or "").strip().upper() or None
            linha = {"conjunto": nome, "perfil": avaliado.get("ID_PONTO"), "grupo": grupo,
                     "origem": origem, "alterados": alterados, "registrada": reg}
            # referência: núcleo corrigido sobre os símbolos verdadeiros
            if verdadeiro is not None:
                rv = AV.classificar(FX._perfil(verdadeiro))
                linha["ref"] = {"classe": rv.classe, "conclusivo": rv.conclusivo, "alc": _alc(rv)}
                linha["simbolos_verdadeiros"] = {str(k): verdadeiro["HORIZONTES"][k]["SIMB_HORIZ"]
                                                 for k in alterados}
            # A0: núcleo original, sem as correções
            AV.CORRECOES_INTEGRACAO = False
            try:
                r0 = AV.classificar(FX._perfil(avaliado))
                linha["A0"] = {"classe": r0.classe, "conclusivo": r0.conclusivo, "alc": _alc(r0)}
            finally:
                AV.CORRECOES_INTEGRACAO = True
            det = FX.detector_de_referencia(avaliado.get("ID_PONTO"))
            for v, inf in infs.items():
                cfg = FX.Configuracao(inferidor=inf, detector=det, explicador_numerico=numerico,
                                      recomendar=recomendar and v == "A")
                try:
                    s = FX.executar(avaliado, cfg)
                    linha[v] = _resumo_saida(s)
                except Exception as exc:  # falha registrada, não escondida
                    import traceback
                    linha[v] = {"falha": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc()[-2000:]}
            if nome == "E4":
                linha["curadoria"] = _trocas_curadoria(avaliado)
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
            f.flush()
            if n % 25 == 0:
                print(f"{nome}: {n} perfis, {time.time() - t0:.0f}s", flush=True)
    print(f"{nome}: {n} perfis em {time.time() - t0:.0f}s → {caminho}")
    return caminho


def _leituras(simbolo):
    s = (simbolo or "").strip()
    m = gs.moderniza(s)
    ls = [m] if m else (gs.leituras(s) or [s])
    out = []
    for l in ls:
        a = gs.analisa(l)
        if a.reconhecido and not a.mesclado and a.principal:
            out.append((a.principal, frozenset(x.rstrip(gs.MACRON) for x in a.sufixos)))
    return out


def _trocas_curadoria(item: dict) -> dict:
    """Trocas substantivas de símbolo (critério de inferidor.avaliacao)."""
    from inferidor.dados import SUFIXOS_LIDOS
    curado = {a["horizonte"]: a["curado"] for a in item.get("_ALTERACOES", [])
              if a["campo"] == "SIMB_HORIZ"}
    saida = {}
    for k, h in enumerate(item.get("HORIZONTES") or []):
        orig = [(p, s & set(SUFIXOS_LIDOS)) for p, s in _leituras(h.get("SIMB_HORIZ"))]
        if not orig:
            continue
        fin = [(p, s & set(SUFIXOS_LIDOS)) for p, s in _leituras(curado.get(k, h.get("SIMB_HORIZ")))]
        subst = bool(fin) and all(o != fin[0] for o in orig)
        saida[str(k)] = {"original": h.get("SIMB_HORIZ"), "curado": curado.get(k, h.get("SIMB_HORIZ")),
                         "substantiva": subst,
                         "assinatura_curada": [assinatura(curado[k])[0], sorted(assinatura(curado[k])[1])]
                         if k in curado else None}
    return saida


# ---------------------------------------------------------------- agregação --

def _boot(grupos, fn, reps=REPS, semente=SEMENTE_BOOT):
    rng = random.Random(semente)
    por = defaultdict(list)
    for i, g in enumerate(grupos):
        por[g].append(i)
    chaves = list(por)
    vals = []
    for _ in range(reps):
        idx = [i for g in (rng.choice(chaves) for _ in chaves) for i in por[g]]
        vals.append(fn(idx))
    vals.sort()
    return vals[int(0.025 * reps)], vals[int(0.975 * reps) - 1]


def _mcnemar(b: int, c: int) -> float:
    """p bilateral exato (binomial) para b × c discordantes."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def _resposta(lin, v):
    """A melhor resposta disponível na variante: observacional se conclusiva;
    senão a condicional do cenário 1 (MARCADA como condicional)."""
    r = lin[v]
    if r["obs"]["conclusivo"]:
        return r["obs"]["classe"], "observacional"
    if r.get("cond") and r["cond"]["conclusivo"]:
        return r["cond"]["classe"], "condicional"
    return None, None


def agregar() -> dict:
    res = {}
    for arq in sorted(SAIDA.glob("E*.jsonl")):
        linhas = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
        nome = arq.stem
        falhas = {v: sum("falha" in l[v] for l in linhas) for v in "ABC"}
        ok = [l for l in linhas if all("falha" not in l[v] for v in "ABC")]
        R = {"perfis": len(linhas), "falhas": falhas, "avaliados": len(ok)}
        grupos = [l["grupo"] for l in ok]
        R["grupos"] = len(set(grupos))
        # invariância e correções
        R["M8_invariancia_observacional"] = sum(l["A"]["obs_sha"] == l["B"]["obs_sha"] == l["C"]["obs_sha"]
                                                for l in ok)
        R["M8_invariancia_versao"] = sum(l["A"]["versao_sha"] == l["B"]["versao_sha"] == l["C"]["versao_sha"]
                                         for l in ok)
        R["verificacoes_violadas"] = {v: sum(not all(l[v]["verificacoes"].values()) for l in ok) for v in "ABC"}
        dif0 = [l for l in ok if (l["A0"]["classe"], l["A0"]["conclusivo"], l["A0"]["alc"]) !=
                (l["A"]["obs"]["classe"], l["A"]["obs"]["conclusivo"], l["A"]["obs"]["alc"])]
        R["efeito_correcoes_A0_x_A"] = {"perfis_com_saida_diferente": len(dif0),
                                        "exemplos": [(l["perfil"], l["A0"]["classe"], l["A0"]["alc"],
                                                      l["A"]["obs"]["classe"], l["A"]["obs"]["alc"])
                                                     for l in dif0[:8]]}
        com_ref = [l for l in ok if l.get("ref")]
        if com_ref:
            R["M5_ref_no_alcancavel_A"] = [sum(l["ref"]["classe"] in l["A"]["obs"]["alc"]
                                               for l in com_ref if l["ref"]["classe"]),
                                           sum(1 for l in com_ref if l["ref"]["classe"])]
            R["M5_ref_no_alcancavel_A0"] = [sum(l["ref"]["classe"] in l["A0"]["alc"]
                                                for l in com_ref if l["ref"]["classe"]),
                                            sum(1 for l in com_ref if l["ref"]["classe"])]
        por_v = {}
        for v in "ABC":
            d = {}
            d["horizontes_acionados"] = sum(l[v]["gatilhos"] for l in ok)
            d["propostas"] = sum(l[v]["propostas"] for l in ok)
            ab = Counter(a for l in ok for a in l[v]["abstencoes"])
            d["abstencoes"] = dict(ab)
            d["horizontes_com_proposta"] = d["propostas"] - sum(ab.values())
            d["candidatos"] = sum(l[v]["candidatos"] for l in ok)
            d["candidatos_bem_formados"] = sum(l[v]["candidatos_bem_formados"] for l in ok)
            d["cenarios"] = sum(l[v]["cenarios"] for l in ok)
            d["cenarios_compativeis"] = sum(l[v]["compativeis"] for l in ok)
            d["incompatibilidades"] = Counter(x.split(":")[0] if "fora do conjunto" not in x else "fora do alcançável"
                                              for l in ok for inc in l[v]["incompativeis"] for x in inc).most_common(8)
            d["violacoes_contencao"] = sum(len(l[v]["violacoes_contencao"]) for l in ok)
            nao_concl = [l for l in ok if not l[v]["obs"]["conclusivo"]]
            d["obs_nao_conclusivos"] = len(nao_concl)
            d["M3_resolvidos_cond_cenario1"] = sum(bool(l[v]["cond"] and l[v]["cond"]["conclusivo"]) for l in nao_concl)
            d["M3_resolvidos_cond_robusta"] = sum(bool(l[v]["robusta"]) for l in nao_concl)
            alvo = (lambda l: l["ref"]["classe"]) if com_ref else (lambda l: l["registrada"])
            cc = [l for l in nao_concl if l[v]["cond"] and l[v]["cond"]["conclusivo"]]
            d["M4_cond_concordantes"] = sum(l[v]["cond"]["classe"] == alvo(l) for l in cc)
            d["M4_cond_discordantes"] = sum(l[v]["cond"]["classe"] != alvo(l) for l in cc)
            rob = [l for l in nao_concl if l[v]["robusta"]]
            d["M4_robusta_concordantes"] = sum(l[v]["cond"]["classe"] == alvo(l) for l in rob)
            d["M4_referencia"] = ("classe com os símbolos verdadeiros" if com_ref else
                                  "ORDEM registrada (referência fraca)")
            d["M4_ref_alcancavel_cond"] = sum(alvo(l) in (l[v]["cond"]["alc"] if l[v]["cond"] else l[v]["obs"]["alc"])
                                              for l in ok if alvo(l))
            d["conflitos_sinalizados"] = sum(len(l[v]["conflitos"]) for l in ok)
            d["divergentes_explicador"] = sum((l[v]["explicador"] or "").startswith("divergência") for l in ok)
            d["hip_anotacao_geradas"] = sum(len(l[v]["hip_anotacao"]) for l in ok)
            d["hip_anotacao_verificadas"] = sum(sum(h["verificada"] for h in l[v]["hip_anotacao"]) for l in ok)
            d["perfis_com_hip_anotacao_verificada"] = sum(any(h["verificada"] for h in l[v]["hip_anotacao"])
                                                          for l in ok)
            t = sorted(l[v]["tempo_s"] for l in ok)
            d["tempo_medio_s"] = sum(t) / len(t) if t else 0
            d["tempo_mediano_s"] = t[len(t) // 2] if t else 0
            d["tempo_p95_s"] = t[int(0.95 * (len(t) - 1))] if t else 0
            por_v[v] = d
        R["variantes"] = por_v
        # comparações pareadas sobre a melhor resposta disponível
        alvo = (lambda l: l["ref"]["classe"]) if com_ref else (lambda l: l["registrada"])
        base = [l for l in ok if alvo(l)]
        gb = [l["grupo"] for l in base]

        def ind(l, v, tipo):
            c, _ = _resposta(l, v)
            if tipo == "certa":
                return int(c is not None and c == alvo(l))
            if tipo == "errada":
                return int(c is not None and c != alvo(l))
            return int(c is not None)
        comp = {}
        for a_, b_ in (("B", "A"), ("C", "A"), ("B", "C")):
            linha = {}
            for tipo in ("certa", "errada", "resolvida"):
                xa = [ind(l, a_, tipo) for l in base]
                xb = [ind(l, b_, tipo) for l in base]
                dif = sum(xa) - sum(xb)
                lo, hi = _boot(gb, lambda idx: sum(xa[i] - xb[i] for i in idx) / max(1, len(idx)))
                bb = sum(1 for x, y in zip(xa, xb) if x and not y)
                cc_ = sum(1 for x, y in zip(xa, xb) if y and not x)
                linha[tipo] = {"n": len(base), a_: sum(xa), b_: sum(xb), "diferenca": dif,
                               "diferenca_por_perfil": dif / max(1, len(base)),
                               "ic95_por_grupo": [lo, hi], "discordantes": [bb, cc_],
                               "mcnemar_p": _mcnemar(bb, cc_)}
            comp[f"{a_}_vs_{b_}"] = linha
        R["comparacoes_pareadas"] = comp
        R["comparacoes_referencia"] = ("classe com os símbolos verdadeiros" if com_ref
                                       else "ORDEM registrada (referência fraca)")
        if nome == "E4":
            R["E4"] = _agrega_e4(ok)
        res[nome] = R
    (SAIDA / "resumo.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str),
                                       encoding="utf-8")
    return res


def _agrega_e4(ok) -> dict:
    out = {}
    for v in "BC":
        tp = fp = n_subst = n_sem = 0
        prop_ok = prop_n = prop_abst = 0
        acerto = {1: 0, 3: 0}
        acerto_h = {1: 0, 3: 0}
        casos = 0
        for l in ok:
            cur = l["curadoria"]
            flag = {c["h"] for c in l[v]["conflitos"]}
            gat = {p["horizonte_id"]: p for p in l[v]["propostas_topo"]}
            for k, info in cur.items():
                if k in gat:
                    if info["substantiva"]:
                        prop_n += 1
                        p = gat[k]
                        if p["abstencao"]:
                            prop_abst += 1
                        elif info["assinatura_curada"] and p["topo"]:
                            a = assinatura(p["topo"])
                            prop_ok += int([a[0], sorted(a[1])] == info["assinatura_curada"])
                    continue
                if info["substantiva"]:
                    n_subst += 1
                    tp += int(k in flag)
                else:
                    n_sem += 1
                    fp += int(k in flag)
            # Acerto@k: perfis divergentes cuja curadoria trocou símbolo substantivamente
            if (l[v]["explicador"] or "").startswith("divergência"):
                trocados = {k: i for k, i in cur.items() if i["substantiva"]}
                if trocados:
                    casos += 1
                    verif = [h for h in l[v]["hip_anotacao"] if h["verificada"]]
                    for kk in (1, 3):
                        top = verif[:kk]
                        acerto_h[kk] += int(any(h["horizonte_id"] in trocados for h in top))
                        acerto[kk] += int(any(h["horizonte_id"] in trocados and
                                              [assinatura(h["simbolo_hipotetico"])[0],
                                               sorted(assinatura(h["simbolo_hipotetico"])[1])]
                                              == trocados[h["horizonte_id"]]["assinatura_curada"]
                                              for h in top))
        out[v] = {"conflito_tp": [tp, n_subst], "conflito_falso_alerta": [fp, n_sem],
                  "falso_alerta_wilson": list(wilson(fp, n_sem)) if n_sem else None,
                  "propostas_em_horizontes_acionados_com_troca": {"n": prop_n, "abstencoes": prop_abst,
                                                                  "assinatura_igual_a_curada": prop_ok},
                  "acerto_at_k": {"casos_de_referencia": casos, "horizonte_e_assinatura": acerto,
                                  "so_horizonte": acerto_h}}
    out["numericas_identicas_entre_variantes"] = sum(
        l["A"]["hip_numericas"] == l["B"]["hip_numericas"] == l["C"]["hip_numericas"] for l in ok)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=("rodar", "agregar"))
    ap.add_argument("conjunto", nargs="?")
    ap.add_argument("--limite", type=int, default=0)
    a = ap.parse_args(argv)
    if a.acao == "rodar":
        rodar(a.conjunto, a.limite)
    else:
        print(json.dumps(agregar(), ensure_ascii=False, indent=1, default=str)[:20000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
