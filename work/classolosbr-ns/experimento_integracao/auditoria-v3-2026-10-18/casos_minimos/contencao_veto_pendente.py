"""Contenção sob preenchimento compatível do dado que deixa um veto PENDENTE.

Universo: todo perfil do BDSolos (sem o curado) e do conjunto curado com ao
menos uma identificação de origem "veto pendente" (plíntico sem cor ou sem
espessura determinada; B latossólico de espessura não determinada).

Preenchimentos compatíveis (o dado ausente pode ter qualquer um destes valores):
  P1 profundidade — todo horizonte aberto (LIMITE_INF ≥ 10000 ou ausente) passa a
     terminar a LIMITE_SUP + X, X ∈ {5, 20, 60, 150}, respeitado o mínimo observado;
  P2 cor da matriz ausente num horizonte com plíntico pendente — matriz clara
     (10YR 7/1) ou não clara (2.5YR 4/6);
  P4 argila ausente (motivo do B nítico pendente) — 100, 350 ou 650 g/kg em todos os horizontes sem argila;
  P3 mosqueado registrado sem matiz ou sem croma — completado claro (10YR, croma 1)
     ou não claro (2.5YR, croma 6).
Propriedade: alcançável(preenchido) ⊆ alcançável(observado), na 5ª e na 6ª.

    python contencao_veto_pendente.py [--sem-correcoes] [--limite N]
"""
import argparse, copy, json, sys, time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "dags")); sys.path.insert(0, str(RAIZ.parents[1] / "tools"))
import nucleo.avaliador as AV
from nucleo.edicoes import chave_de
from nucleo.horizontes import identificar
from integracao import fluxo as FX

ap = argparse.ArgumentParser(); ap.add_argument("--sem-correcoes", action="store_true"); ap.add_argument("--limite", type=int, default=0)
a = ap.parse_args()
AV.CORRECOES_INTEGRACAO = not a.sem_correcoes
alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())


def brutos():
    import bdsolos_adapter as B
    perfis, _ = B.ler_perfis()
    for p in B.filtrar(perfis, sem_curado=True):
        yield "BDSolos", p
    pasta = RAIZ.parents[1] / "raw" / "pykka7-smartsolos-dataset"
    for x in sorted(pasta.rglob("*.json")):
        if not x.name.endswith("_all.json"):
            yield "curado", json.JSONDecoder().raw_decode(x.read_text(encoding="utf-8"))[0]["items"][0]


def preenchimentos(b, pend):
    hs = b["HORIZONTES"]
    abertos = [k for k, h in enumerate(hs) if (h.get("LIMITE_INF") is None or float(h.get("LIMITE_INF") or 0) >= 10000)
               and h.get("LIMITE_SUP") is not None]
    for X in (5, 20, 60, 150):
        if abertos:
            q = copy.deepcopy(b)
            for k in abertos:
                q["HORIZONTES"][k]["LIMITE_INF"] = float(q["HORIZONTES"][k]["LIMITE_SUP"]) + X
            yield f"P1 aberto +{X} cm", q
    sem_argila = [k for k, h in enumerate(hs) if h.get("ARGILA") is None]
    if sem_argila:
        for v in (100, 350, 650):
            q = copy.deepcopy(b)
            for k in sem_argila:
                q["HORIZONTES"][k]["ARGILA"] = v
            yield f"P4 argila ausente = {v} g/kg", q
    for k in pend:
        h = hs[k]
        if h.get("COR_UMIDA_MATIZ") is None or h.get("COR_UMIDA_CROMA") is None:
            for nome, (m, v, c) in (("clara", ("10YR", 7, 1)), ("não clara", ("2.5YR", 4, 6))):
                q = copy.deepcopy(b)
                q["HORIZONTES"][k].update({"COR_UMIDA_MATIZ": m, "COR_UMIDA_VALOR": v, "COR_UMIDA_CROMA": c})
                yield f"P2 matriz {nome} em {h.get('SIMB_HORIZ')}", q
        for i in (1, 2, 3):
            mm, cc = h.get(f"COR_MOSQ_MATIZ_{i}"), h.get(f"COR_MOSQ_CROMA_{i}")
            if (mm is None) != (cc is None):
                for nome, (m, c) in (("claro", ("10YR", 1)), ("não claro", ("2.5YR", 6))):
                    q = copy.deepcopy(b)
                    if mm is None: q["HORIZONTES"][k][f"COR_MOSQ_MATIZ_{i}"] = m
                    if cc is None: q["HORIZONTES"][k][f"COR_MOSQ_CROMA_{i}"] = c
                    yield f"P3 mosqueado {i} {nome} em {h.get('SIMB_HORIZ')}", q


t0 = time.time()
cont = Counter(); motivos = Counter(); viol = []
for fonte, b in brutos():
    if a.limite and cont["perfis"] >= a.limite:
        break
    trab = copy.deepcopy(b)
    for k, h in enumerate(trab["HORIZONTES"]):
        h["_ID_HORIZ"] = str(k)
    p = FX._perfil(trab)
    pend = sorted({int(i.horizonte.get("_ID_HORIZ")) for i in identificar(p) if "veto pendente" in i.origem})
    if not pend:
        continue
    for i in identificar(p):
        if "veto pendente" in i.origem:
            motivos[(i.tipo, i.observacao.split(" (")[0][:60])] += 1
    cont["perfis"] += 1; cont[f"perfis_{fonte}"] += 1
    for ed in ("5", "6"):
        A = alc(AV.classificar(p, chave_de(ed)))
        for rot, q in preenchimentos(trab, pend):
            cont["preenchimentos"] += 1
            r = AV.classificar(FX._perfil(q), chave_de(ed))
            fora = alc(r) - A
            if fora:
                viol.append({"perfil": b.get("ID_PONTO"), "edicao": ed, "preenchimento": rot,
                             "observado": sorted(A), "preenchido": r.resumo(), "fora": sorted(fora)})
print(json.dumps({"correcoes": AV.CORRECOES_INTEGRACAO, "segundos": round(time.time() - t0),
                  **cont, "perfis_com_violacao": len({(v["perfil"], v["edicao"]) for v in viol}),
                  "violacoes": len(viol)}, ensure_ascii=False))
print("motivos de veto pendente (tipo, observação):", motivos.most_common(10))
for v in viol[:20]:
    print("  ", v)
