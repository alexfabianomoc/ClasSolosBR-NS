"""Testes da integração (cópia experimental).

    python -m integracao.testes            # todos
    python -m integracao.testes --rapido   # sem os que carregam os modelos reais

Casos reais do conjunto curado e casos sintéticos pequenos. Um estimador falso
(`EstimadorFalso`) controla as probabilidades para exercitar acionamento,
abstenção, múltiplos candidatos, incompatibilidade e conflito sem depender do
que os modelos reais aprenderam.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "dags"))

from inferidor import dados as D  # noqa: E402
from nucleo import avaliador as AV  # noqa: E402
from nucleo.avaliador import classificar  # noqa: E402

from . import fluxo as FX  # noqa: E402
from .inferidor import GATILHO_AUSENTE, GATILHO_SEM_TIPO, Inferidor, gatilho  # noqa: E402

PYKKA7 = RAIZ.parents[1] / "raw" / "pykka7-smartsolos-dataset"
FALHAS: list[str] = []
N = [0]


def confere(cond, msg):
    N[0] += 1
    print(("  ok   " if cond else "  FALHA ") + msg)
    if not cond:
        FALHAS.append(msg)


def curado(nome: str) -> dict:
    a = next(PYKKA7.rglob(f"{nome}.json"))
    return json.JSONDecoder().raw_decode(a.read_text(encoding="utf-8"))[0]["items"][0]


def mascarar_b(item: dict, novo: str = "B") -> dict:
    m = copy.deepcopy(item)
    for h in m["HORIZONTES"]:
        s = h.get("SIMB_HORIZ") or ""
        if s.startswith("Bt") and "f" not in s and "g" not in s:
            h["SIMB_HORIZ"] = novo
    return m


class EstimadorFalso:
    """Mesmas probabilidades para todo horizonte; `sufixos` = {letra: p}."""

    def __init__(self, principal="B", sufixos=None, theta=0.6, tau=0.5, ident="falso-1"):
        self.id, self.nome, self.theta, self.tau = ident, "falso", theta, tau
        self.classes = ["A", "B", "C", "outro"]
        self.limiares = np.full(len(D.SUFIXOS_LIDOS), 0.5)
        self._pp = np.array([0.02, 0.02, 0.02, 0.02])
        self._pp[self.classes.index(principal)] = 0.94
        self._ps = np.array([0.01] * len(D.SUFIXOS_LIDOS))
        for s, p in (sufixos or {}).items():
            self._ps[D.SUFIXOS_LIDOS.index(s)] = p

    def proba(self, linhas):
        n = len(linhas)
        return np.tile(self._pp, (n, 1)), np.tile(self._ps, (n, 1))


def falso(**kw) -> Inferidor:
    return Inferidor(EstimadorFalso(**kw))


def cfg(inf=None, **kw) -> FX.Configuracao:
    base = dict(inferidor=inf, recomendar=False, explicador_numerico=False)
    base.update(kw)
    return FX.Configuracao(**base)


def _sem_tempo(s):
    s = copy.deepcopy(s)
    s.pop("tempo_s", None)
    return s


# ----------------------------------------------------------------- testes --

def teste_correcoes():
    print("\ncorreções do núcleo (C1 símbolo ausente, C2 truncamento, C3 pendentes na agregação)")
    pe1 = curado("GeoTab_PE_001_Lagoa_dos_Gatos")
    k = next(i for i, h in enumerate(pe1["HORIZONTES"]) if h["SIMB_HORIZ"] == "Bt1")
    apagado = copy.deepcopy(pe1)
    apagado["HORIZONTES"][k]["SIMB_HORIZ"] = ""
    alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())
    AV.CORRECOES_INTEGRACAO = False
    r0 = classificar(FX._perfil(apagado))
    AV.CORRECOES_INTEGRACAO = True
    r1 = classificar(FX._perfil(apagado))
    confere("ARGISSOLO" not in alc(r0), f"C1 regressão: sem a correção, apagar o Bt1 do PE_001 tira ARGISSOLO ({r0.resumo()})")
    confere("ARGISSOLO" in alc(r1), f"C1: com a correção, ARGISSOLO continua alcançável ({r1.resumo()})")

    rn7 = curado("GeoTab_RN_007_Acu")
    k = next(i for i, h in enumerate(rn7["HORIZONTES"]) if h["SIMB_HORIZ"] == "Bt2")
    m = copy.deepcopy(rn7)
    m["HORIZONTES"][k]["SIMB_HORIZ"] = "B"
    AV.CORRECOES_INTEGRACAO = False
    r0 = classificar(FX._perfil(m))
    AV.CORRECOES_INTEGRACAO = True
    r1 = classificar(FX._perfil(m))
    confere("ARGISSOLO" not in alc(r0), f"C3 regressão: sem a correção, Bt2 → B tira ARGISSOLO do RN_007 ({r0.resumo()})")
    confere("ARGISSOLO" in alc(r1), f"C3: com a correção, ARGISSOLO continua alcançável ({r1.resumo()})")

    # C4: predicado derivado com B sem tipo (caso real da rodada v1)
    try:
        sys.path.insert(0, str(RAIZ.parents[1] / "tools"))
        import bdsolos_adapter as B
        perfis, _ = B.ler_perfis()
        p598 = next(x for x in B.filtrar(perfis, sem_curado=True)
                    if x["ID_PONTO"] == "BDSolos|598|5818|Perfil no 11")
        m = copy.deepcopy(p598)
        for h in m["HORIZONTES"]:
            if h["SIMB_HORIZ"] in ("Bt1", "Bt2"):
                h["SIMB_HORIZ"] = "B"
        AV.CORRECOES_INTEGRACAO = False
        r0 = classificar(FX._perfil(m))
        AV.CORRECOES_INTEGRACAO = True
        r1 = classificar(FX._perfil(m))
        confere("ARGISSOLO" not in alc(r0), f"C4 regressão: sem a correção, ARGISSOLO refutado ({r0.resumo()})")
        confere("ARGISSOLO" in alc(r1), f"C4: com a correção, ARGISSOLO alcançável ({r1.resumo()})")
    except (FileNotFoundError, StopIteration) as exc:
        confere(True, f"C4: BDSolos indisponível ({type(exc).__name__}); teste pulado")

    # C2: cinco horizontes com V calculado (44,9%) e V do boletim (55%) em lados
    # opostos de 50% → 2^5 = 32 combinações > MAX_VARIANTES.
    sint = {"ID_PONTO": "sint-truncamento", "HORIZONTES": []}
    for j in range(5):
        sint["HORIZONTES"].append({"SIMB_HORIZ": "A" if j == 0 else f"C{j}", "LIMITE_SUP": 10 * j,
                                   "LIMITE_INF": 10 * j + 10, "CA_TROC": 2, "MG_TROC": 1,
                                   "K_TROC": 0.3, "NA_TROC": 0.2, "H_TROC": 3.5, "AL_TROC": 0.8,
                                   "_V_BOLETIM": 55, "ARGILA": 200})
    p = FX._perfil(sint)
    v = AV._variantes_de_leitura(p)
    confere(v.total == 32 and v.truncado and len(v) == AV.MAX_VARIANTES,
            f"C2: {v.total} combinações > {AV.MAX_VARIANTES} → marcado como truncado")
    d = AV._avaliar_por_leitura(AV.r.Residual(), p, v)
    confere(d.valor is AV.I, "C2: regra sob truncamento sai indeterminada, mesmo a residual")
    AV.CORRECOES_INTEGRACAO = False
    d0 = AV._avaliar_por_leitura(AV.r.Residual(), p, AV._variantes_de_leitura(p))
    AV.CORRECOES_INTEGRACAO = True
    confere(d0.valor is AV.V, "C2 regressão: sem a correção, as 16 primeiras decidiam pelas 32")


def teste_acionamento_e_abstencao():
    print("\nacionamento e abstenção do Inferidor")
    confere(gatilho("B") == GATILHO_SEM_TIPO and gatilho("2B") == GATILHO_SEM_TIPO, "B e 2B acionam (sem tipo)")
    confere(gatilho("") == GATILHO_AUSENTE, "símbolo ausente aciona")
    confere(gatilho("Bt2") is None and gatilho("Ap") is None and gatilho("BA") is None,
            "Bt2, Ap e BA não acionam")
    m = mascarar_b(curado("GeoTab_PE_001_Lagoa_dos_Gatos"))
    s = FX.executar(m, cfg(falso(sufixos={"t": 0.97})))
    props = s["inferencia"]["propostas"]
    confere(props and all(p["candidatos"][0]["simbolo"].endswith("Bt") for p in props),
            "com p_t alto, o candidato 1 é Bt (complementação do B anotado)")
    confere(all(p["abstencao"] is None for p in props), "κ alto: sem abstenção")
    s2 = FX.executar(m, cfg(falso(sufixos={"t": 0.55, "w": 0.45}, theta=0.9)))
    confere(all(p["abstencao"] and "κ" in p["abstencao"] for p in s2["inferencia"]["propostas"]),
            "κ abaixo de θ: abstenção com motivo")
    confere(s2["condicional"]["cenarios"] == [], "com abstenção em todos os horizontes, nenhum cenário")
    s3 = FX.executar(m, cfg(falso(sufixos={})))
    confere(all("não informa o tipo" in (p["abstencao"] or "") for p in s3["inferencia"]["propostas"]),
            "nenhum sufixo de tipo decidido: abstenção ('não informa o tipo')")
    s_g = FX.executar(m, cfg(falso(sufixos={"t": 0.95, "g": 0.70, "c": 0.6}, theta=0.0)))
    simb = [c["simbolo"] for p in s_g["inferencia"]["propostas"] for c in p["candidatos"]]
    confere(simb and not any(x in s for s in simb for x in "gcfv"),
            f"complementação de B sem tipo não acrescenta g, c, f nem v ({sorted(set(simb))})")
    s4 = FX.executar(curado("GeoTab_PE_001_Lagoa_dos_Gatos"), cfg(falso(sufixos={"t": 0.97})))
    confere(s4["inferencia"]["status"].startswith("não acionado"),
            "perfil com todos os símbolos informativos: Inferidor não acionado")
    ap = copy.deepcopy(curado("GeoTab_PE_001_Lagoa_dos_Gatos"))
    ap["HORIZONTES"][3]["SIMB_HORIZ"] = ""
    s5 = FX.executar(ap, cfg(falso(principal="outro", sufixos={"t": 0.9})))
    confere(any("outro" in (p["abstencao"] or "") for p in s5["inferencia"]["propostas"]),
            "símbolo ausente com principal 'outro': abstenção")


def teste_preservacao_e_invariancia():
    print("\npreservação da entrada, do símbolo anotado e da resposta observacional")
    m = mascarar_b(curado("GeoTab_PE_003_Camocim_de_Sao_Felix"))
    antes = json.dumps(m, sort_keys=True)
    s_off = FX.executar(m, cfg(None))
    s_on = FX.executar(m, cfg(falso(sufixos={"w": 0.95})))
    confere(json.dumps(m, sort_keys=True) == antes, "a entrada não é modificada")
    confere(all(s_on["verificacoes"].values()), f"verificações finais: {s_on['verificacoes']}")
    confere(s_off["observacional"] == s_on["observacional"],
            "resposta observacional idêntica com o Inferidor ligado e desligado")
    confere(s_off["versao"] == s_on["versao"], "Camada de Versão idêntica com e sem Inferidor")
    for c in s_on["condicional"]["cenarios"]:
        for sub in c["substituicoes"]:
            confere(m["HORIZONTES"][int(sub["horizonte_id"])]["SIMB_HORIZ"] == sub["simbolo_anotado"],
                    f"símbolo anotado preservado no horizonte {sub['horizonte_id']} "
                    f"(inferido {sub['simbolo_inferido']} só no cenário)")
            break
        break
    det = FX.detector_de_referencia("GeoTab_PE_003_Camocim_de_Sao_Felix")
    s_det = FX.executar(m, cfg(None, detector=det))
    confere(s_det["observacional"] == s_off["observacional"],
            "o Sentinela (escore de anomalia) não altera a decisão simbólica")
    a, b = FX.executar(m, cfg(falso(sufixos={"w": 0.95}))), FX.executar(m, cfg(falso(sufixos={"w": 0.95})))
    confere(_sem_tempo(a) == _sem_tempo(b), "reprodutibilidade: mesma entrada, mesma saída")


def teste_rastreabilidade():
    print("\nrastreabilidade da classe condicional")
    m = mascarar_b(curado("GeoTab_PE_001_Lagoa_dos_Gatos"))
    s = FX.executar(m, cfg(falso(sufixos={"t": 0.97}, ident="falso-rastreio")))
    c = s["condicional"]
    confere(c["classe_condicional"] == "ARGISSOLO", f"classe condicional ARGISSOLO ({c['resumo_cenario_1']})")
    confere(s["observacional"]["classe"] != "ARGISSOLO" or not s["observacional"]["conclusivo"],
            "a resposta observacional não conclui ARGISSOLO (a classe só existe como condicional)")
    cen = c["cenarios"][0]
    confere(cen["condicional"] and "CONDICIONAL" in cen["aviso"], "cenário marcado como condicional")

    def marcas(no):
        out = list(no.get("simbolos_inferidos", []))
        for f in no.get("filhos", []):
            out += marcas(f)
        return out
    ms = marcas(cen["resultado"]["prova"])
    confere(bool(ms), "a árvore de prova marca nós que dependem de símbolo inferido")
    if ms:
        mk = ms[0]
        confere(mk["modelo"] == "falso-rastreio" and mk["cenario"] == 1
                and "confianca_de_tipo_kappa" in mk and mk["simbolo_inferido"].endswith("Bt"),
                f"a marca traz modelo, cenário, κ e símbolo inferido ({mk['simbolo_anotado']} → {mk['simbolo_inferido']})")
        confere("escore_de_ordenacao_nao_calibrado" in mk, "o escore é declarado não calibrado")


def teste_incompatibilidade():
    print("\nsímbolo inferido incompatível com os dados")
    sint = {"ID_PONTO": "sint-veto", "ORDEM": "CAMBISSOLO", "HORIZONTES": [
        {"SIMB_HORIZ": "A", "LIMITE_SUP": 0, "LIMITE_INF": 20, "ARGILA": 200},
        {"SIMB_HORIZ": "B", "LIMITE_SUP": 20, "LIMITE_INF": 35, "ARGILA": 250},
        {"SIMB_HORIZ": "C", "LIMITE_SUP": 35, "LIMITE_INF": 100, "ARGILA": 240}]}
    s = FX.executar(sint, cfg(falso(sufixos={"w": 0.97})))
    cen = s["condicional"]["cenarios"]
    confere(cen and not cen[0]["compativel"] and any("vetado" in x for x in cen[0]["incompatibilidade"]),
            f"Bw em B de 15 cm: o núcleo veta o B latossólico e o cenário é incompatível "
            f"({cen[0]['incompatibilidade'] if cen else '—'})")
    confere(s["condicional"]["classe_condicional"] is None,
            "cenário incompatível não gera classe condicional")


def teste_multiplos_candidatos():
    print("\nmúltiplos candidatos e orçamento de cenários")
    m = mascarar_b(curado("GeoTab_PE_002_Goiana"))
    s = FX.executar(m, cfg(falso(sufixos={"t": 0.62, "w": 0.58, "i": 0.40}, theta=0.5)))
    props = s["inferencia"]["propostas"]
    confere(all(len(p["candidatos"]) >= 2 for p in props), "probabilidades próximas: ≥ 2 candidatos por horizonte")
    confere(all(len(p["candidatos"]) <= 3 for p in props), "no máximo 3 candidatos por horizonte")
    c = s["condicional"]
    confere(c["cenarios_avaliados"] <= 8, f"no máximo 8 cenários ({c['cenarios_avaliados']} de {c['combinacoes_possiveis']})")
    esc = [x["escore_de_ordenacao_nao_calibrado"] for x in c["cenarios"]]
    confere(esc == sorted(esc, reverse=True), "cenários ordenados pelo escore de ordenação")
    confere(not c["violacoes_de_contencao"], "nenhum cenário sai do conjunto alcançável observacional")


def teste_conflito_e_explicador():
    print("\nconflitos encaminhados ao Explicador e hipóteses verificadas pelo núcleo")
    # Divergência sintética: registra-se LATOSSOLO num Argissolo curado.
    pe1 = curado("GeoTab_PE_001_Lagoa_dos_Gatos")
    s = FX.executar(pe1, cfg(falso(sufixos={"w": 0.99}, tau=0.5), classe_registrada="LATOSSOLO"))
    confere(s["explicador"]["status"].startswith("divergência"), "LATOSSOLO registrado fica fora do alcançável")
    confere(len(s["conflitos_de_anotacao"]["sinalizados"]) > 0, "o conflito anotado (Bt) × proposto (Bw) é sinalizado")
    hip = s["explicador"]["hipoteses_de_anotacao"]
    confere(isinstance(hip, list) and hip, "hipóteses de anotação geradas")
    ver = [h for h in hip if h["verificada"]]
    if ver:
        h = ver[0]
        copia = copy.deepcopy(pe1)
        copia["HORIZONTES"][int(h["horizonte_id"])]["SIMB_HORIZ"] = h["simbolo_hipotetico"]
        r = classificar(FX._perfil(copia))
        confere(r.classe == "LATOSSOLO", f"hipótese verificada ({h['simbolo_anotado']} → "
                                         f"{h['simbolo_hipotetico']}) reexecutada dá LATOSSOLO")
        confere("não comprova" in h["natureza"], "a hipótese é apresentada como contrafactual, não como causa")
    nao = [h for h in hip if not h["verificada"]]
    confere(all(h["classe_obtida"] != "LATOSSOLO" for h in nao), "hipóteses não verificadas não restabelecem")
    confere(s["observacional"]["classe"] == "ARGISSOLO", "o conflito não altera a classe observacional")
    confere("escalas" in s["explicador"], "hipóteses numéricas e de anotação em listas separadas")
    cats = s["versao"]["categorias"]
    confere(any("anteriores à 5ª NÃO excluída" in c for c in cats),
            "a Camada de Versão nunca exclui defasagem de edições anteriores")
    # Erro de anotação simulado: Bt1 → Bi1 no PE_001 leva a CAMBISSOLO; a ficha diz ARGISSOLO.
    k = next(i for i, h in enumerate(pe1["HORIZONTES"]) if h["SIMB_HORIZ"] == "Bt1")
    errado = copy.deepcopy(pe1)
    errado["HORIZONTES"][k]["SIMB_HORIZ"] = "Bi1"
    s3 = FX.executar(errado, cfg(falso(sufixos={"t": 0.99}, tau=0.5)))
    confere(s3["observacional"]["classe"] == "CAMBISSOLO" and
            s3["explicador"]["status"].startswith("divergência"),
            "Bi1 anotado: o núcleo deriva CAMBISSOLO e a ficha (ARGISSOLO) diverge")
    ver = [h for h in s3["explicador"]["hipoteses_de_anotacao"] if h["verificada"]]
    confere(bool(ver) and ver[0]["horizonte_id"] == str(k) and ver[0]["simbolo_hipotetico"].startswith("Bt"),
            f"hipótese de anotação verificada no horizonte trocado ({ver[0]['simbolo_anotado'] if ver else '—'}"
            f" → {ver[0]['simbolo_hipotetico'] if ver else '—'})")
    if ver:
        c = copy.deepcopy(errado)
        c["HORIZONTES"][k]["SIMB_HORIZ"] = ver[0]["simbolo_hipotetico"]
        confere(classificar(FX._perfil(c)).classe == "ARGISSOLO",
                "reexecução independente confirma: a hipótese restabelece ARGISSOLO")
    confere(errado["HORIZONTES"][k]["SIMB_HORIZ"] == "Bi1", "o símbolo anotado (Bi1) não foi sobrescrito")
    s_a = FX.executar(pe1, cfg(None, classe_registrada="LATOSSOLO"))
    confere(isinstance(s_a["explicador"]["hipoteses_de_anotacao"], dict),
            "variante sem Inferidor: nenhuma hipótese de anotação")


def teste_edicoes():
    print("\ndivergências entre edições na Camada de Versão")
    s = FX.executar(curado("GeoTab_PE_025_Barreiros"), cfg(None))
    v = s["versao"]
    confere(v["saidas_diferem"], f"PE_025: as saídas das bases diferem ({v['sob_5a']} × {v['sob_6a']})")
    confere(any("edições comparadas" in c or "bases diferem" in c for c in v["categorias"]),
            f"categoria de diferença entre edições presente ({v['categorias'][:2]})")


def teste_indisponibilidade():
    print("\nindisponibilidade do modelo")
    m = mascarar_b(curado("GeoTab_PE_001_Lagoa_dos_Gatos"))
    s = FX.executar(m, cfg(Inferidor(None, "teste")))
    confere(s["status"] == "ok", "o fluxo segue sem o modelo")
    confere(all("indisponível" in p["abstencao"] for p in s["inferencia"]["propostas"]),
            "toda proposta vira abstenção 'modelo indisponível'")
    confere(s["observacional"] == FX.executar(m, cfg(None))["observacional"],
            "a resposta observacional permanece disponível e idêntica")
    i = FX.inferidor_padrao("nao-existe")
    confere(i is not None and not i.disponivel, "artefato inexistente: Inferidor marcado indisponível, sem exceção")

    class Quebrado(EstimadorFalso):
        def proba(self, linhas):
            raise RuntimeError("falha simulada")
    s2 = FX.executar(m, cfg(Inferidor(Quebrado())))
    confere(s2["status"] == "ok" and all("falha do modelo" in p["abstencao"]
                                         for p in s2["inferencia"]["propostas"]),
            "exceção do modelo vira abstenção com motivo")


def teste_contencao_preenchimento():
    print("\nconsistência do conjunto alcançável sob preenchimento compatível")
    alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())
    for nome in ("GeoTab_PE_001_Lagoa_dos_Gatos", "GeoTab_RN_007_Acu", "GeoTab_PE_031_Itambe"):
        it = curado(nome)
        m = mascarar_b(it)
        if m == it:
            continue
        A = alc(classificar(FX._perfil(m)))
        ks = [k for k, h in enumerate(m["HORIZONTES"]) if h["SIMB_HORIZ"] == "B"]
        viol = []
        for s in ("Bt", "Bw", "Bi", "Bh", "Bs"):
            c = copy.deepcopy(m)
            for k in ks:
                c["HORIZONTES"][k]["SIMB_HORIZ"] = s
            r = classificar(FX._perfil(c))
            if not alc(r) <= A:
                viol.append((s, sorted(alc(r) - A)))
        confere(not viol, f"{nome}: todo preenchimento B→Bt/Bw/Bi/Bh/Bs fica no alcançável mascarado {viol or ''}")
    it = curado("GeoTab_PE_003_Camocim_de_Sao_Felix")
    k = next(i for i, h in enumerate(it["HORIZONTES"]) if h["SIMB_HORIZ"].startswith("Bt"))
    ap = copy.deepcopy(it)
    ap["HORIZONTES"][k]["SIMB_HORIZ"] = ""
    A = alc(classificar(FX._perfil(ap)))
    viol = []
    for s in ("Bt", "Bw", "A", "C", "E", "BA", "Bg", "Cg", it["HORIZONTES"][k]["SIMB_HORIZ"]):
        c = copy.deepcopy(ap)
        c["HORIZONTES"][k]["SIMB_HORIZ"] = s
        r = classificar(FX._perfil(c))
        if not alc(r) <= A:
            viol.append((s, sorted(alc(r) - A)))
    confere(not viol, f"PE_003, símbolo apagado: preenchimentos ficam no alcançável {viol or ''}")


def teste_contencao_ablacao():
    print("\ncontenção sob ablação de atributos (núcleo corrigido)")
    from nucleo.avaliacao_parcial import GRUPOS, remover
    alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())
    viol, n = [], 0
    for a in sorted(PYKKA7.rglob("*.json"))[:40]:
        if a.name.endswith("_all.json"):
            continue
        from nucleo.perfil import carregar_json
        p = carregar_json(a)[0]
        r = classificar(p)
        if not r.conclusivo:
            continue
        for g, atributos in GRUPOS.items():
            n += 1
            if r.classe not in alc(classificar(remover(p, atributos))):
                viol.append((p.id_ponto, g))
    confere(not viol, f"{n} remoções de grupo em perfis conclusivos: contenção {n - len(viol)}/{n} {viol[:3]}")


def teste_recomendacao():
    print("\npróxima determinação preservada")
    it = curado("GeoTab_RN_007_Acu")
    s_a = FX.executar(it, FX.Configuracao(inferidor=None, recomendar=True, k_doadores=5,
                                          explicador_numerico=False))
    s_b = FX.executar(it, FX.Configuracao(inferidor=falso(sufixos={"t": 0.9}), recomendar=True,
                                          k_doadores=5, explicador_numerico=False))
    confere("doadores" in s_a["proxima_determinacao"], "recomendação produzida para perfil não conclusivo")
    confere(s_a["proxima_determinacao"] == s_b["proxima_determinacao"],
            "a recomendação não depende do Inferidor (calculada sobre os dados observados)")
    confere(s_a["proxima_determinacao"].get("violacoes_de_contencao") == 0,
            "nenhum desfecho simulado fora do conjunto alcançável")


def teste_auditoria_v3():
    print("\nauditoria v3: C5, escopo da C4 e robustez sob orçamento")
    alc = lambda r: set(r.alcancaveis) | ({r.classe} if r.classe else set())
    from nucleo.edicoes import chave_de

    def h(s, a, b, **kw):
        d = {"SIMB_HORIZ": s, "LIMITE_SUP": a, "LIMITE_INF": b, "ARGILA": 450,
             "AREIA_GROS": 200, "AREIA_FINA": 150, "SILTE": 200}
        d.update(kw)
        return d
    # C5 — B latossólico válido só no contexto da sequência
    caso = {"ID_PONTO": "min-C5", "HORIZONTES": [h("A", 0, 15), h("Bwg1", 15, 40),
                                                 h("Bw2", 40, 80), h("C", 80, 160)]}
    for ed in "56":
        AV.CORRECOES_INTEGRACAO = False
        r0 = classificar(FX._perfil(caso), chave_de(ed))
        AV.CORRECOES_INTEGRACAO = True
        r1 = classificar(FX._perfil(caso), chave_de(ed))
        confere(r0.classe == "GLEISSOLO", f"C5 regressão ({ed}ª): sem a correção, GLEISSOLO apesar de 65 cm de Bw ({r0.resumo()})")
        confere(r1.classe == "LATOSSOLO" and "GLEISSOLO" not in alc(r1),
                f"C5 ({ed}ª): 'existe B diagnóstico' no contexto do perfil — LATOSSOLO ({r1.resumo()})")
    # Escopo da C4: o veto pendente do plíntico é tratado pelo próprio predicado
    pend = {"ID_PONTO": "min-C4-escopo", "HORIZONTES": [
        h("A", 0, 15), h("Btf", 15, 40, COR_UMIDA_MATIZ=None), h("Bt2", 40, 100)]}
    from nucleo.horizontes import identificar, requisitos_argissolos_5ed
    p = FX._perfil(pend)
    origens = {(i.horizonte.simbolo, i.tipo): i.origem for i in identificar(p)}
    confere("pendente" in origens.get(("Btf", "plíntico"), ""), "Btf sem cor: plíntico com veto pendente")
    v, det = requisitos_argissolos_5ed(p)
    confere(v is AV.I, f"requisitos dos Argissolos com plíntico pendente → indeterminado ({det})")
    A = alc(classificar(p))
    for nome, cor in (("clara + mosqueado claro", {"COR_UMIDA_MATIZ": "10YR", "COR_UMIDA_VALOR": 7,
                                                    "COR_UMIDA_CROMA": 1}),
                      ("vermelha sem mosqueado", {"COR_UMIDA_MATIZ": "2.5YR", "COR_UMIDA_VALOR": 4,
                                                  "COR_UMIDA_CROMA": 6})):
        q = copy.deepcopy(pend)
        q["HORIZONTES"][1].update(cor)
        r = classificar(FX._perfil(q))
        confere(alc(r) <= A, f"preenchimento compatível da cor ({nome}) fica no alcançável observacional "
                             f"({r.resumo()} ⊆ {sorted(A)})")
    # Robustez sob orçamento: 3 horizontes × 3 candidatos = 27 > 8 cenários
    m = mascarar_b(curado("GeoTab_PE_003_Camocim_de_Sao_Felix"))
    s = FX.executar(m, cfg(falso(sufixos={"t": 0.62, "w": 0.58, "i": 0.40}, theta=0.5)))
    c = s["condicional"]
    confere(c["combinacoes_possiveis"] > c["cenarios_avaliados"] and not c["avaliacao_completa"],
            f"orçamento estourado é declarado ({c['aviso_orcamento']})")
    confere(c["condicional_robusta"] is False, "com avaliação incompleta, a robustez não é afirmada")


def teste_modelos_reais():
    print("\nmodelos reais (artefatos de experimento_integracao/modelos)")
    from .modelos import Estimador, carregar
    for nome in ("rede", "arvores"):
        try:
            e = carregar(nome)
        except FileNotFoundError:
            confere(False, f"artefato {nome} ausente — rode `python -m integracao.modelos treinar`")
            continue
        confere(e.meta["atributos"] == D.nomes_atributos() and len(e.meta["atributos"]) == 81,
                f"{nome}: 81 atributos, mesma ordem do treino")
        m = mascarar_b(curado("GeoTab_PE_001_Lagoa_dos_Gatos"))
        s = FX.executar(m, cfg(Inferidor(e)))
        confere(s["status"] == "ok" and all(s["verificacoes"].values()),
                f"{nome}: fluxo completo com o modelo real, verificações OK")
        props = s["inferencia"]["propostas"]
        confere(all(c["bem_formado"] or c["achados_gramatica"] for p in props for c in p["candidatos"]),
                f"{nome}: todo candidato tem a boa-formação conferida")
    import joblib
    import tempfile
    pac = joblib.load(RAIZ / "experimento_integracao" / "modelos" / "rede.joblib")
    pac["meta"]["atributos"] = pac["meta"]["atributos"][::-1]
    with tempfile.TemporaryDirectory() as d:
        caminho = Path(d) / "rede.joblib"
        joblib.dump(pac, caminho)
        try:
            Estimador(caminho)
            confere(False, "atributos em outra ordem deveriam ser recusados")
        except ValueError:
            confere(True, "artefato com atributos em outra ordem é recusado (compatibilidade treino × inferência)")


def main(argv=None) -> int:
    rapido = "--rapido" in (argv or sys.argv[1:])
    testes = [teste_correcoes, teste_acionamento_e_abstencao, teste_preservacao_e_invariancia,
              teste_rastreabilidade, teste_incompatibilidade, teste_multiplos_candidatos,
              teste_conflito_e_explicador, teste_edicoes, teste_indisponibilidade,
              teste_contencao_preenchimento, teste_contencao_ablacao, teste_recomendacao,
              teste_auditoria_v3]
    if not rapido:
        testes.append(teste_modelos_reais)
    for t in testes:
        try:
            t()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            FALHAS.append(f"{t.__name__}: exceção {type(exc).__name__}: {exc}")
    print(f"\n{N[0]} verificações; {len(FALHAS)} falha(s)")
    for f in FALHAS:
        print("  -", f)
    return 1 if FALHAS else 0


if __name__ == "__main__":
    raise SystemExit(main())
