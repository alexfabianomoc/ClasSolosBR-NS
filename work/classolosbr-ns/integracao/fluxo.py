"""O fluxo integrado — a API interna que coordena os seis componentes.

    from integracao.fluxo import Configuracao, executar
    saida = executar(perfil_bruto, Configuracao(inferidor=...))

Ordem das operações e por quê (confirmada contra o código e a §4.1):

1. **Validação** e cópia da entrada. O original nunca é tocado; tudo o que
   segue trabalha numa cópia, e a preservação é conferida no fim.
2. **Sentinela** — gramática do símbolo e escore de anomalia. Sinaliza; não
   entra em nenhuma decisão (o escore só ordena hipóteses numéricas).
3. **Núcleo, resposta observacional** — classe, conjunto alcançável,
   pendências, árvore de prova. Calculada antes de qualquer inferência e
   nunca alterada por ela (invariância conferida nos testes).
4. **Camada de Versão** — o mesmo perfil sob a 5ª e a 6ª edições.
5. **Inferidor** — só nos horizontes com símbolo ausente, B sem tipo ou
   leituras discordantes. Propõe símbolos (ou se abstém).
6. **Núcleo, cenários condicionais** — cada combinação limitada de símbolos
   propostos é reexecutada numa cópia do perfil; a classe que sair é
   CONDICIONAL e a árvore de prova identifica símbolo, modelo, confiança e
   cenário.
7. **Conflitos anotado × proposto** — nos horizontes de símbolo informativo;
   viram hipóteses de anotação, nunca alteram símbolo nem classe.
8. **Explicador** — quando a classe registrada sai do conjunto alcançável:
   hipóteses numéricas e de anotação, em listas separadas, todas verificadas
   por reexecução; consulta à Camada de Versão para a natureza da divergência.
9. **Avaliador Parcial** — próxima determinação, se a resposta observacional
   não é conclusiva. Os doadores só simulam desfechos.
10. **Procedência** — cada bloco diz de onde vem; verificações de invariantes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "dags"))

from nucleo import avaliador as AV  # noqa: E402
from nucleo.avaliador import Derivacao, classificar  # noqa: E402
from nucleo.edicoes import COBERTURA, COMUM, EXCLUSIVA, ROTULO, chave_de, cotejar  # noqa: E402
from nucleo.horizontes import identificar  # noqa: E402
from nucleo.logica import F, I, V  # noqa: E402
from nucleo.perfil import _aplicar_profundidade_observada, de_dicionario  # noqa: E402
from sentinela import gramatica_sufixos as gs  # noqa: E402

from .inferidor import Inferidor, Proposta, assinatura, gatilho  # noqa: E402

ID = "_ID_HORIZ"
VERSAO_FLUXO = "integracao-1.1 (auditoria v3, 2026-10-18)"


@dataclass
class Configuracao:
    edicao: str = "5"
    inferidor: Inferidor | None = None        # None ⇒ variante sem inferência aprendida
    max_horizontes_inferidos: int = 6
    max_cenarios: int = 8
    conflitos_de_anotacao: bool = True
    explicar: bool = True
    explicador_numerico: bool = True
    max_hipoteses_anotacao: int = 30
    recomendar: bool = True
    k_doadores: int = 15
    detector: object | None = None            # sentinela.anomalia.DetectorAnomalia ajustado
    classe_registrada: str | None = None      # padrão: ORDEM do perfil

    @property
    def variante(self) -> str:
        if self.inferidor is None:
            return "sem inferência aprendida"
        return f"com Inferidor {self.inferidor.id}"


# ------------------------------------------------------------ utilidades --

def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def _alc(r) -> set[str]:
    return set(r.alcancaveis) | ({r.classe} if r.classe else set())


def arvore(d: Derivacao | None, anotar=None) -> dict | None:
    """Árvore de prova serializável; `anotar(no)` devolve marcas extras."""
    if d is None:
        return None
    no = {"rotulo": d.rotulo, "valor": d.valor.value, "detalhe": d.detalhe,
          "horizonte": d.horizonte, "atributo": d.atributo, "fonte": d.fonte}
    if d.distancia is not None:
        no["distancia"] = d.distancia
    if anotar:
        marcas = anotar(d)
        if marcas:
            no["simbolos_inferidos"] = marcas
    no["filhos"] = [arvore(f, anotar) for f in d.filhos]
    return no


def resultado(r, anotar=None) -> dict:
    return {"classe": r.classe, "conclusivo": r.conclusivo, "alcancaveis": sorted(_alc(r)),
            "alcancaveis_alem_da_classe": list(r.alcancaveis), "resumo": r.resumo(),
            "pendencias": list(dict.fromkeys(r.pendencias)),
            "prova": arvore(r.derivacao, anotar),
            "prova_texto": r.derivacao.texto() if r.derivacao else None,
            "refutadas": [{"classe": c, "rupturas": [f"{n.rotulo} — {n.detalhe}" if n.detalhe
                                                     else n.rotulo for n in d.folhas_falhas()[:3]]}
                          for c, d in r.refutadas]}


# ------------------------------------------------------------- validação --

NUMERICOS_CONTRATO = ("LIMITE_SUP", "LIMITE_INF", "ARGILA", "SILTE", "AREIA_GROS", "AREIA_FINA",
                      "CA_TROC", "MG_TROC", "K_TROC", "NA_TROC", "H_TROC", "AL_TROC", "PH_AGUA",
                      "PH_KCL", "C_ORG", "COR_UMIDA_VALOR", "COR_UMIDA_CROMA")


def validar(bruto) -> tuple[list[str], list[str]]:
    erros, avisos = [], []
    if not isinstance(bruto, dict):
        return ["a entrada não é um objeto de perfil"], avisos
    hs = bruto.get("HORIZONTES")
    if not isinstance(hs, list) or not hs:
        return ["perfil sem lista de horizontes"], avisos
    for k, h in enumerate(hs):
        if not isinstance(h, dict):
            erros.append(f"horizonte {k}: não é um objeto")
            continue
        for c in NUMERICOS_CONTRATO:
            v = h.get(c)
            if v is None or v == "" or isinstance(v, (int, float)) and not isinstance(v, bool):
                continue
            try:
                float(v)
            except (TypeError, ValueError):
                avisos.append(f"horizonte {k}: {c} = {v!r} não é número — tratado como ausente")
        if not str(h.get("SIMB_HORIZ") or "").strip():
            avisos.append(f"horizonte {k}: símbolo ausente — nenhuma classe é refutada por isso "
                          "(supervalorização sobre o catálogo de leituras)")
    if not bruto.get("ID_PONTO"):
        avisos.append("perfil sem ID_PONTO")
    return erros, avisos


# --------------------------------------------------------------- Sentinela --

def sentinela(perfil, detector) -> dict:
    gram = []
    for h in perfil.horizontes:
        achados = [{"codigo": a.codigo, "gravidade": a.gravidade, "mensagem": a.mensagem}
                   for a in gs.valida(h.simbolo) if a.gravidade in ("erro", "alerta", "suspeita")]
        moderno = gs.moderniza(h.simbolo)
        if achados or moderno:
            gram.append({"horizonte_id": h.get(ID), "simbolo": h.simbolo, "achados": achados,
                         "leitura_atual_sugerida": moderno})
    anomalias = []
    if detector is not None:
        for i, h in enumerate(perfil.horizontes):
            for a, v in h.atributos.items():
                if isinstance(v, bool) or not isinstance(v, (int, float)) or a.startswith("_"):
                    continue
                s = detector.escore(perfil, i, a)
                if s >= 0.5:
                    anomalias.append({"horizonte_id": h.get(ID), "simbolo": h.simbolo,
                                      "atributo": a, "valor": v, "sigma": round(s, 3)})
        anomalias.sort(key=lambda x: -x["sigma"])
    return {"procedencia": "Sentinela de Qualidade de Dados (gramática de Larach et al. 1988; "
                           "escore z robusto)",
            "afeta_a_decisao": False, "gramatica": gram, "anomalias": anomalias[:20],
            "nota": "alertas e escores não alteram a decisão simbólica; o escore só ordena "
                    "hipóteses numéricas no Explicador"}


# -------------------------------------------------------- Camada de Versão --

def versao(perfil, reg) -> tuple[dict, object]:
    cot = cotejar(perfil)
    causas = {"5": cot.causas("5"), "6": cot.causas("6")}
    cat = []
    a5, a6 = _alc(cot.sob_5a), _alc(cot.sob_6a)
    if reg:
        if (reg in a5) != (reg in a6) or (cot.divergem and reg in a5 | a6):
            cat.append("alteração entre as edições comparadas (5ª × 6ª)")
        if reg not in a5 and reg not in a6:
            cat.append("possível erro de dado ou de formalização comum às duas bases "
                       "(o cotejo não distingue um do outro)")
    todas = [m for d in causas.values() for m in d.values()]
    if COMUM in todas:
        cat.append("insuficiência dos dados para critério comum às duas bases")
    if EXCLUSIVA in todas:
        cat.append("insuficiência dos dados em critério em que as bases diferem")
    if COBERTURA in todas:
        cat.append("cobertura incompleta da formalização (ordem apenas triada)")
    # Escopo (decisão de 2026-10-18): edições anteriores à 5ª estão fora do foco da
    # pesquisa; permanece só a ressalva de que o cotejo 5ª × 6ª nada diz sobre elas.
    cat.append("defasagem em relação a edições anteriores à 5ª NÃO excluída: estão fora do "
               "escopo deste trabalho, e a concordância 5ª × 6ª nada diz sobre elas")
    return ({"procedencia": "Camada de Versão (nucleo.edicoes.cotejar)",
             "sob_5a": cot.sob_5a.resumo(), "sob_6a": cot.sob_6a.resumo(),
             "saidas_diferem": cot.divergem, "causas_da_nao_conclusao": causas,
             "diagnostico": cot.diagnostico(reg), "categorias": cat,
             "ressalva": "compara implementações (chave5.py × chave6.py), não as edições em si"},
            cot)


# ------------------------------------------------- inferência condicional --

def _gatilhos(trabalho: dict) -> dict[int, str]:
    return {k: g for k, h in enumerate(trabalho["HORIZONTES"])
            if (g := gatilho(h.get("SIMB_HORIZ") or "")) is not None}


def _perfil(bruto: dict):
    p = de_dicionario(bruto)
    _aplicar_profundidade_observada(p)
    return p


def _anotador(subst: dict[str, dict], perfil_c):
    """Marca, na árvore de prova, os nós que dependem de símbolo inferido."""
    simbolos = {}
    for h in perfil_c.horizontes:
        hid = h.get(ID)
        if hid in subst:
            simbolos.setdefault(h.simbolo, []).append(subst[hid])
    anotados = {h.simbolo for h in perfil_c.horizontes if h.get(ID) not in subst}

    def anotar(no: Derivacao):
        marcas = []
        for s, lista in simbolos.items():
            texto = f"{no.horizonte or ''} {no.detalhe or ''}"
            if no.horizonte == s or any(tok.strip(",;:()") == s for tok in texto.split()):
                for m in lista:
                    marca = dict(m)
                    if s in anotados:
                        marca["ambiguidade"] = (f"o símbolo {s} também ocorre anotado em outro "
                                                "horizonte do perfil")
                    marcas.append(marca)
        return marcas
    return anotar


def cenarios(trabalho: dict, perfil_obs, res_obs, propostas: list[Proposta], cfg) -> dict:
    ativas = [p for p in propostas if not p.abstencao]
    descartadas = []
    if len(ativas) > cfg.max_horizontes_inferidos:
        ativas.sort(key=lambda p: -max(c.kappa for c in p.candidatos if c.bem_formado))
        descartadas = [p.horizonte_id for p in ativas[cfg.max_horizontes_inferidos:]]
        ativas = ativas[:cfg.max_horizontes_inferidos]
    if not ativas:
        return {"status": "nenhuma proposta (abstenção em todos os horizontes acionados)",
                "cenarios": [], "classe_condicional": None}
    listas = [[c for c in p.candidatos if c.bem_formado] for p in ativas]
    combos = sorted(product(*listas), key=lambda cs: -math.prod(c.escore for c in cs))
    total = math.prod(len(x) for x in listas)
    combos = combos[:cfg.max_cenarios]
    A_obs = _alc(res_obs)
    saida = []
    for n, cs in enumerate(combos, 1):
        copia = copy.deepcopy(trabalho)
        subst = {}
        for p, c in zip(ativas, cs):
            k = int(p.horizonte_id)
            h = copia["HORIZONTES"][k]
            subst[p.horizonte_id] = {
                "cenario": n, "horizonte_id": p.horizonte_id,
                "profundidade_cm": [h.get("LIMITE_SUP"), h.get("LIMITE_INF")],
                "simbolo_anotado": p.simbolo_anotado, "simbolo_inferido": c.simbolo,
                "forma": c.forma, "gatilho": p.gatilho, "modelo": p.modelo,
                "confianca_de_tipo_kappa": round(c.kappa, 4),
                "p_principal": round(c.p_principal, 4),
                "p_sufixos_de_tipo": {s: c.p_sufixos[s] for s in "twihsvfgc" if s in c.p_sufixos},
                "escore_de_ordenacao_nao_calibrado": c.escore}
            h["SIMB_HORIZ"] = c.simbolo
        perfil_c = _perfil(copia)
        r = classificar(perfil_c, chave_de(cfg.edicao))
        vetos = []
        for idf in identificar(perfil_c):
            hid = idf.horizonte.get(ID)
            if hid in subst and "vetado" in idf.origem:
                vetos.append(f"{idf.horizonte.simbolo}: {idf.tipo} vetado pelo dado"
                             + (f" ({idf.observacao})" if idf.observacao else ""))
        fora = sorted(_alc(r) - A_obs)
        compativel = not vetos and not fora
        saida.append({
            "cenario": n, "condicional": True,
            "substituicoes": list(subst.values()),
            "escore_de_ordenacao_nao_calibrado": math.prod(c.escore for c in cs),
            "compativel": compativel,
            "incompatibilidade": vetos + ([f"saída fora do conjunto alcançável observacional: {fora}"]
                                          if fora else []),
            "resultado": resultado(r, _anotador(subst, perfil_c)),
            "aviso": ("CLASSE CONDICIONAL: válida apenas se os símbolos inferidos forem "
                      "confirmados; confiança do modelo não é prova normativa")})
    compat = [c for c in saida if c["compativel"]]
    topo = compat[0]["resultado"] if compat else None
    classes = {c["resultado"]["classe"] for c in compat if c["resultado"]["conclusivo"]}
    # Auditoria v3: com orçamento estourado (mais combinações que cenários
    # avaliados, ou horizontes deixados sem inferência), a robustez não pode
    # ser afirmada — os cenários não avaliados poderiam dar outra classe.
    completa = total <= len(saida) and not descartadas
    robusta = (completa and bool(compat) and all(c["resultado"]["conclusivo"] for c in compat)
               and len(classes) == 1)
    uniao = sorted({x for c in compat for x in c["resultado"]["alcancaveis"]})
    return {"status": "cenários avaliados", "procedencia": "Núcleo sobre cópias do perfil com "
            "símbolos propostos pelo Inferidor",
            "avaliacao_completa": completa,
            "aviso_orcamento": None if completa else (
                f"avaliados {len(saida)} de {total} cenários"
                + (f"; horizontes sem inferência por orçamento: {descartadas}" if descartadas else "")
                + " — robustez não afirmada"),
            "uniao_alcancaveis_cenarios_compativeis": uniao,
            "combinacoes_possiveis": total, "cenarios_avaliados": len(saida),
            "horizontes_nao_inferidos_por_orcamento": descartadas,
            "cenarios": saida,
            "classe_condicional": (topo["classe"] if topo and topo["conclusivo"] else None),
            "resumo_cenario_1": topo["resumo"] if topo else None,
            "condicional_robusta": robusta,
            "violacoes_de_contencao": [c["cenario"] for c in saida
                                       if any("fora do conjunto" in x for x in c["incompatibilidade"])],
            "aviso": "classes condicionais não são conclusões dos dados observados"}


# ---------------------------------------------------------------- Explicador --

def hipoteses_de_anotacao(trabalho, reg, cfg, conflitos, propostas) -> list[dict]:
    pedidos = []
    for c in sorted(conflitos, key=lambda c: (not c["conflito"], -c["sinal"])):
        for cand in c["candidatos"][:3]:
            pedidos.append((c["horizonte_id"], c["simbolo_anotado"], cand["simbolo"], cand["forma"],
                            "conflito anotado × proposto" if c["conflito"]
                            else "proposta divergente abaixo de τ", c["sinal"], cand["escore"]))
    for p in propostas:
        if p.abstencao:
            continue
        for cand in p.candidatos[:3]:
            if cand.bem_formado:
                pedidos.append((p.horizonte_id, p.simbolo_anotado, cand.simbolo, cand.forma,
                                f"proposta para {p.gatilho}", None, cand.escore))
    vistos, saida = set(), []
    for hid, anot, prop, forma, origem, sinal, esc in pedidos:
        if (hid, prop) in vistos or len(saida) >= cfg.max_hipoteses_anotacao:
            continue
        vistos.add((hid, prop))
        copia = copy.deepcopy(trabalho)
        copia["HORIZONTES"][int(hid)]["SIMB_HORIZ"] = prop
        r = classificar(_perfil(copia), chave_de(cfg.edicao))
        saida.append({"horizonte_id": hid, "simbolo_anotado": anot, "simbolo_hipotetico": prop,
                      "forma": "substituição" if forma == "proposta completa" else forma,
                      "origem": origem, "sinal_de_conflito": sinal,
                      "escore_do_modelo_nao_calibrado": esc,
                      "verificada": r.classe == reg, "classe_obtida": r.classe,
                      "resumo_obtido": r.resumo(),
                      "natureza": "contrafactual suficiente verificado pelo núcleo — não comprova "
                                  "que a anotação esteja errada" if r.classe == reg else
                                  "não restabelece a classe registrada"})
    saida.sort(key=lambda h: (not h["verificada"], h["origem"] != "conflito anotado × proposto",
                              -(h["sinal_de_conflito"] or 0), -h["escore_do_modelo_nao_calibrado"]))
    return saida


def explicador(perfil, trabalho, res_obs, reg, cfg, conflitos, propostas) -> dict:
    from nucleo.explicador import explicar
    if not reg:
        return {"status": "sem classe registrada — nada a explicar"}
    A = _alc(res_obs)
    if res_obs.conclusivo and res_obs.classe == reg:
        return {"status": "a classe registrada é a derivada — sem divergência"}
    if reg in A:
        return {"status": "incompletude, e não divergência: a classe registrada continua "
                          "alcançável (cabe ao Avaliador Parcial)"}
    saida = {"status": "divergência: a classe registrada está fora do conjunto alcançável",
             "procedencia": "Explicador de Divergências (abdução contrastiva, |Aj| = 1, "
                            "toda hipótese verificada por reexecução do núcleo)"}
    if cfg.explicador_numerico:
        exp = explicar(perfil, reg, chave_de(cfg.edicao),
                       sentinela=cfg.detector.escore if cfg.detector else None)
        if exp is None:
            saida["hipoteses_numericas"] = {"status": "classe registrada fora da chave implementada"}
        else:
            saida["origem_da_refutacao"] = ("condição da classe registrada falsa" if exp.origem == 1
                                            else "classe precedente concluída antes")
            saida["rupturas"] = [f"{n.rotulo} — {n.detalhe}" if n.detalhe else n.rotulo
                                 for n in exp.rupturas[:5]]
            saida["hipoteses_numericas"] = [
                {"atributo": h.atributo, "horizonte": h.horizonte, "indice": h.indice,
                 "valor_informado": h.valor_informado, "valor_proposto": h.valor_proposto,
                 "deslocamento_decimal": h.tipico, "escore": round(h.escore, 4),
                 "componentes": h.componentes, "verificada": True,
                 "natureza": "contrafactual suficiente — não comprova a causa real"}
                for h in exp.hipoteses[:10]]
    else:
        saida["hipoteses_numericas"] = {"status": "desligadas nesta execução (idênticas entre variantes)"}
    saida["hipoteses_de_anotacao"] = (hipoteses_de_anotacao(trabalho, reg, cfg, conflitos, propostas)
                                      if cfg.inferidor is not None else
                                      {"status": "sem Inferidor nesta variante"})
    saida["escalas"] = ("hipóteses numéricas e de anotação em listas separadas: o escore s(h) e o "
                        "escore do modelo não são comparáveis")
    return saida


# --------------------------------------------------------- Avaliador Parcial --

def proxima_determinacao(perfil, res_obs, cfg) -> dict:
    from nucleo.medicao import recomendar
    if res_obs.conclusivo:
        return {"status": "resposta observacional conclusiva — nada a recomendar"}
    if not cfg.recomendar:
        return {"status": "desligada nesta execução (idêntica entre variantes)"}
    rec = recomendar(perfil, chave_de(cfg.edicao), k=cfg.k_doadores)
    return {"procedencia": "Avaliador Parcial (nucleo.medicao: ganho de informação simulado com "
                           "doadores do BDSolos)",
            "candidatas": [{"horizonte": c.horizonte, "unidade": c.unidade,
                            "ganho_bits": round(c.ganho, 4), "p_concluir": round(c.p_concluir, 3)}
                           for c in rec.candidatas if c.ganho > 0][:5],
            "sem_campo_no_contrato": rec.sem_campo, "violacoes_de_contencao": len(rec.violacoes),
            "doadores": "valores de horizontes doadores usados SÓ para simular desfechos da medição; "
                        "não entram em nenhum resultado do perfil"}


# --------------------------------------------------------------------- fluxo --

def executar(bruto: dict, cfg: Configuracao | None = None) -> dict:
    cfg = cfg or Configuracao()
    t0 = time.perf_counter()
    original_sha = _sha(bruto)
    erros, avisos = validar(bruto)
    saida = {"versao_fluxo": VERSAO_FLUXO, "variante": cfg.variante,
             "edicao": ROTULO.get(cfg.edicao, cfg.edicao),
             "perfil": (bruto or {}).get("ID_PONTO") if isinstance(bruto, dict) else None,
             "entrada": {"sha256": original_sha, "erros": erros, "avisos": avisos}}
    if erros:
        saida["status"] = "entrada inválida"
        return saida
    trabalho = copy.deepcopy(bruto)
    for k, h in enumerate(trabalho["HORIZONTES"]):
        h[ID] = str(k)
    perfil = _perfil(trabalho)
    reg = cfg.classe_registrada or (bruto.get("ORDEM") or None)
    reg = reg.strip().upper() if isinstance(reg, str) else None
    classes_chave = {r.classe for r in chave_de(cfg.edicao)}
    saida["classe_registrada"] = {"valor": reg, "na_chave_implementada": reg in classes_chave,
                                  "uso": "só referência para o Explicador; nunca preditor"}
    if reg not in classes_chave:
        reg = None

    saida["sentinela"] = sentinela(perfil, cfg.detector)
    res_obs = classificar(perfil, chave_de(cfg.edicao))
    saida["observacional"] = {"procedencia": "Núcleo Simbólico sobre os dados observados, "
                                             "sem nenhum símbolo inferido",
                              **resultado(res_obs)}
    saida["versao"], _ = versao(perfil, reg)

    gat = _gatilhos(trabalho)
    saida["gatilhos"] = {str(k): g for k, g in gat.items()}
    propostas: list[Proposta] = []
    if cfg.inferidor is None:
        saida["inferencia"] = {"status": "variante sem inferência aprendida"}
        saida["condicional"] = {"status": "não se aplica (sem Inferidor)"}
    elif not gat:
        saida["inferencia"] = {"status": "não acionado: todo horizonte tem símbolo que informa o tipo"}
        saida["condicional"] = {"status": "não acionado"}
    else:
        propostas = cfg.inferidor.propor(trabalho, gat)
        saida["inferencia"] = {"status": "acionado", "modelo": cfg.inferidor.id,
                               "disponivel": cfg.inferidor.disponivel,
                               "propostas": [p.como_dict() for p in propostas],
                               "nota": "o Inferidor devolve símbolos; nunca classe"}
        saida["condicional"] = cenarios(trabalho, perfil, res_obs, propostas, cfg)

    conflitos = []
    if cfg.inferidor is not None and cfg.conflitos_de_anotacao and cfg.inferidor.disponivel:
        ks = [k for k in range(len(trabalho["HORIZONTES"])) if k not in gat]
        conflitos = cfg.inferidor.conflitos(trabalho, ks)
        saida["conflitos_de_anotacao"] = {
            "procedencia": f"Inferidor {cfg.inferidor.id}: 1 − escore(anotado) ≥ τ e assinatura diferente",
            "sinalizados": [c for c in conflitos if c["conflito"]],
            "avaliados": len(conflitos),
            "nota": "hipóteses de anotação: o símbolo anotado é preservado e a classe não muda"}
    if cfg.explicar:
        saida["explicador"] = explicador(perfil, trabalho, res_obs, reg, cfg, conflitos, propostas)
    saida["proxima_determinacao"] = proxima_determinacao(perfil, res_obs, cfg)

    # ------------------------------------------------ verificações finais --
    simbolos_ok = all((h.get("SIMB_HORIZ") or "") == (o.get("SIMB_HORIZ") or "")
                      for h, o in zip(trabalho["HORIZONTES"], bruto["HORIZONTES"]))
    cond = saida.get("condicional", {})
    classes = {r.classe for r in chave_de(cfg.edicao)}
    saida["verificacoes"] = {
        "entrada_preservada": _sha(bruto) == original_sha,
        "simbolos_anotados_intactos": simbolos_ok,
        "condicionais_contidas_no_observacional": not cond.get("violacoes_de_contencao"),
        "inferidor_nao_emite_classe": all(c.simbolo.upper() not in classes
                                          for p in propostas for c in p.candidatos),
        "classe_registrada_usada_so_como_referencia": True,
    }
    saida["status"] = "ok"
    saida["tempo_s"] = round(time.perf_counter() - t0, 4)
    return saida


# ------------------------------------------------------- utilidades de uso --

_detectores: dict = {}


def detector_de_referencia(excluir: str | None = None):
    """Sentinela ajustado nos 94 perfis curados (a referência da §4.2.2),
    sem o perfil `excluir` (para não pontuar um perfil contra si mesmo)."""
    if excluir not in _detectores:
        from sentinela.anomalia import DetectorAnomalia
        from nucleo.perfil import carregar_json
        pasta = RAIZ.parents[1] / "raw" / "pykka7-smartsolos-dataset"
        perfis = [p for a in sorted(pasta.rglob("*.json")) if not a.name.endswith("_all.json")
                  for p in carregar_json(a) if p.id_ponto != excluir]
        _detectores[excluir] = DetectorAnomalia().ajustar(perfis)
    return _detectores[excluir]


def inferidor_padrao(nome: str | None) -> Inferidor | None:
    """'rede', 'arvores' ou None. Falha ao carregar ⇒ Inferidor indisponível."""
    if nome is None:
        return None
    from .modelos import carregar
    try:
        return Inferidor(carregar(nome))
    except Exception as exc:
        return Inferidor(None, f"{type(exc).__name__}: {exc}")
