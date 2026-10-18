#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonda de ablacao da API SmartSolosExpert: quais atributos sao obrigatorios?

O contrato OpenAPI publicado NAO declara nenhum campo como `required` (zero
ocorrencias de "required" nas seis definicoes) e a API nao expoe recurso de
metadados -- so /health, /classification e /verification. A lista de atributos
efetivamente exigidos pela base de regras, portanto, so pode ser obtida por
sondagem: remove-se um campo por vez de perfis que a propria API ja classifica,
e observa-se o que muda.

Automatiza e generaliza o metodo manual de
wiki/outputs/simbolo-de-horizonte-como-entrada-diagnostica.md.

SINAIS DE OBRIGATORIEDADE, do mais forte ao mais fraco:

    ESTRUTURAL  HTTP 500 com "key 'CAMPO' does not exist". O motor Prolog
                dereferencia a chave sem testar se existe e estoura excecao nao
                tratada. O campo e exigido pela implementacao, nao apenas pela
                regra. A mensagem de erro vaza o dicionario interno do horizonte.
    VAZIO       HTTP 200 com corpo `null`: a API nao devolve item nem erro.
                Falha silenciosa -- o cliente le "sem resultado".
    TOTAL       HTTP 200 com ORDEM "unknown": sem o campo a classificacao se
                torna impossivel, mas o motor degrada com elegancia.
    PARCIAL     HTTP 200 com classe diferente da linha de base. Sub-caso
                notavel: colapso para NEOSSOLO (a classe residual) vindo de
                outra ordem.
    INERTE      a carga mudou e a classificacao nao.
    NAO APLIC.  o campo ja era ausente naquele perfil -- a carga enviada e
                identica a da base. NAO conta como inercia: e a licao de metodo
                do Experimento 3 (inercia num slot onde o campo nem existia nao
                prova nada).

LEITURA: "obrigatorio" nao e propriedade global do campo, e sim do par
(campo, caminho taxonomico). Por isso o painel e estratificado por ordem de
solo e o relatorio sai como matriz campo x ordem, nunca como lista unica.

CUSTO: o painel estratificado cabe em UMA requisicao por campo quando nada
falha. Erros 500 custam ~15 s cada e obrigam a isolar perfil a perfil, entao a
sonda so escala para chamadas individuais quando o lote falha.

CREDENCIAIS: AGROAPI_TOKEN, ou AGROAPI_CONSUMER_KEY + AGROAPI_CONSUMER_SECRET,
ou um JSON com {"consumer_key": "...", "consumer_secret": "..."} apontado por
--credenciais (padrao: ~/.agroapi.json, se existir).

USO:

    python tools/agroapi_ablacao.py --simular         # plano e custo, sem rede
    python tools/agroapi_ablacao.py                   # varredura completa
    python tools/agroapi_ablacao.py --por-ordem 2     # painel mais largo
    python tools/agroapi_ablacao.py --campos SIMB_HORIZ,ARGILA --todos
    python tools/agroapi_ablacao.py --modo nulo       # anula em vez de remover
"""

import argparse
import collections
import copy
import json
import os
import re
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "tools"))

import agroapi_verify as av  # noqa: E402  -- plumbing de auth/transporte/carga

NIVEIS_CLASSE = ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")
CRED_PADRAO = os.path.join(os.path.expanduser("~"), ".agroapi.json")
DESCONHECIDO = "unknown"

# Campos que nao entram na varredura: identificador, rotulo de saida, metadados
# do dataset e o proprio vetor de horizontes (remove-lo e degenerado).
NAO_ABLACIONAVEIS = frozenset(
    ("ID_PONTO", "HORIZONTES") + NIVEIS_CLASSE + av.CAMPOS_METADADOS
)

# "key 'SIMB_HORIZ' does not exist in _14146{...}" -- excecao do SWI-Prolog que
# vaza pela API quando a chave e lida sem guarda.
RE_CHAVE_AUSENTE = re.compile(r"key\s+`?'([A-Z0-9_]+)'", re.IGNORECASE)

ESTRUTURAL, VAZIO, TOTAL, PARCIAL, INERTE, RECUSA, ERRO = (
    "estrutural", "vazio", "total", "parcial", "inerte", "recusa", "erro"
)


# ------------------------------------------------------------------ credenciais

def credencial_de(args):
    """Env primeiro; arquivo JSON como alternativa (o segredo nunca e impresso)."""
    if os.environ.get("AGROAPI_TOKEN") or (
        os.environ.get("AGROAPI_CONSUMER_KEY") and os.environ.get("AGROAPI_CONSUMER_SECRET")
    ):
        return av.Credencial.do_ambiente(timeout=args.timeout, verboso=args.verboso)

    caminho = args.credenciais or (CRED_PADRAO if os.path.isfile(CRED_PADRAO) else None)
    if not caminho:
        raise SystemExit(
            "Credenciais ausentes. Defina AGROAPI_TOKEN, ou o par\n"
            "AGROAPI_CONSUMER_KEY + AGROAPI_CONSUMER_SECRET, ou aponte --credenciais\n"
            "para um JSON com consumer_key/consumer_secret. Use --simular para\n"
            "montar o plano sem rede."
        )
    with open(caminho, encoding="utf-8") as fh:
        dados = json.load(fh)
    chave = dados.get("consumer_key") or dados.get("AGROAPI_CONSUMER_KEY")
    segredo = dados.get("consumer_secret") or dados.get("AGROAPI_CONSUMER_SECRET")
    token = dados.get("token") or dados.get("AGROAPI_TOKEN")
    if not token and not (chave and segredo):
        raise SystemExit("%s nao tem consumer_key/consumer_secret nem token." % caminho)
    if args.verboso:
        sys.stderr.write("[auth] credenciais lidas de %s\n" % caminho)
    return av.Credencial(token, chave, segredo, timeout=args.timeout, verboso=args.verboso)


# ------------------------------------------------------------------------ painel

def universo_de_campos(perfis):
    """Campos de horizonte presentes no dataset (com valor nao nulo)."""
    presentes = collections.Counter()
    for perfil in perfis:
        for horiz in perfil.get("HORIZONTES") or []:
            for chave, valor in horiz.items():
                if valor is not None:
                    presentes[chave] += 1
    return [c for c in sorted(presentes) if c not in NAO_ABLACIONAVEIS], presentes


def estratificar(perfis, por_ordem):
    """Ate N perfis por ordem de solo -- cobertura taxonomica com painel pequeno."""
    por_ordem_dict = collections.OrderedDict()
    for perfil in sorted(perfis, key=lambda p: p.get("ID_PONTO") or ""):
        ordem = (perfil.get("ORDEM") or DESCONHECIDO).upper()
        if ordem == DESCONHECIDO.upper():
            continue
        alvo = por_ordem_dict.setdefault(ordem, [])
        if len(alvo) < por_ordem:
            alvo.append(perfil)
    painel = []
    for lista in por_ordem_dict.values():
        painel.extend(lista)
    return painel


def ablacionar(perfil, campo, modo):
    """Devolve (perfil_modificado, mudou). `mudou` distingue inercia de no-op."""
    novo = copy.deepcopy(perfil)
    mudou = False
    for horiz in novo.get("HORIZONTES") or []:
        if horiz.get(campo) is None:
            continue
        if modo == "nulo":
            horiz[campo] = None
        else:
            horiz.pop(campo, None)
        mudou = True
    return novo, mudou


def classe_de(item):
    return tuple((item.get(n) or "").strip() for n in NIVEIS_CLASSE)


def texto_classe(classe):
    return " ".join(x for x in classe if x) or "(vazio)"


def nivel_divergente(base, novo):
    """Nivel mais raso em que as duas classificacoes discordam (1..4), ou 0."""
    for i, (a, b) in enumerate(zip(base, novo), start=1):
        if a != b:
            return i
    return 0


# -------------------------------------------------------------------- requisicao

def montar_carga(perfis, args):
    itens = [av.limpar(p, manter_metadados=False) for p in perfis]
    if not getattr(args, "manter_rotulos", False):
        for item in itens:
            for nivel in NIVEIS_CLASSE:
                item.pop(nivel, None)
    return {"items": itens}


class Sessao(object):
    """Transporte da sonda.

    Diferenca crucial em relacao a agroapi_verify.chamar: aqui um HTTP 500 e
    DADO, nao falha transitoria. Repetir a chamada so gasta 15 s e devolve o
    mesmo estouro do Prolog, entao 500 e 400 nao sao retentados.
    """

    def __init__(self, credencial, args):
        self.credencial = credencial
        self.args = args
        self.requisicoes = 0
        self.transporte = 0
        self.tempo = 0.0

    def post(self, perfis, transporte=3):
        """500 e 400 valem como resposta; falha de transporte e retentada."""
        carga = montar_carga(perfis, self.args)
        codigo, resposta = None, None
        for tentativa in range(1, transporte + 1):
            inicio = time.time()
            self.requisicoes += 1
            codigo, resposta = av.chamar(
                "/classification", self.credencial, carga,
                timeout=self.args.timeout, tentativas=1, verboso=self.args.verboso,
            )
            self.tempo += time.time() - inicio
            if codigo is not None:
                break
            self.transporte += 1
            if self.args.verboso:
                sys.stderr.write("[rede] transporte falhou (%d/%d)\n"
                                 % (tentativa, transporte))
            time.sleep(1.5 * tentativa)
        if self.args.pausa:
            time.sleep(self.args.pausa)
        return codigo, resposta


def mensagem_de_erro(resposta):
    if isinstance(resposta, dict):
        bruto = resposta.get("erro") or resposta.get("_corpo_ilegivel") or ""
        if isinstance(bruto, str):
            try:
                return json.loads(bruto).get("message", bruto)
            except ValueError:
                return bruto
    return str(resposta)


def sondar(sessao, perfis, campo):
    """Classifica o painel ablacionado; isola perfil a perfil so se o lote falhar.

    Devolve {ID_PONTO: {"http": .., "classe": .., "mensagem": ..}}.
    """
    saida = {}
    codigo, resposta = sessao.post(perfis)
    if codigo == 200 and isinstance(resposta, dict) and resposta.get("items"):
        obtidos = {i.get("ID_PONTO"): classe_de(i) for i in resposta["items"]}
        if all(p.get("ID_PONTO") in obtidos for p in perfis):
            for pid, classe in obtidos.items():
                saida[pid] = {"http": 200, "classe": classe, "mensagem": None}
            return saida

    # O lote falhou (ou veio incompleto): o erro pode vir de um unico perfil.
    for perfil in perfis:
        pid = perfil.get("ID_PONTO")
        cod, resp = sessao.post([perfil])
        if cod == 200 and isinstance(resp, dict) and resp.get("items"):
            saida[pid] = {"http": 200, "classe": classe_de(resp["items"][0]),
                          "mensagem": None}
        else:
            msg = mensagem_de_erro(resp)
            saida[pid] = {"http": cod, "classe": None, "mensagem": msg}
            if sessao.args.verboso:
                sys.stderr.write("[api] %s / %s: HTTP %s\n" % (campo, pid, cod))
    return saida


# ---------------------------------------------------------------- classificacao

def categorizar(campo, base, obtido):
    """Traduz o par (linha de base, resposta da ablacao) num dos sinais."""
    http = obtido["http"]
    if http != 200:
        chave = RE_CHAVE_AUSENTE.search(obtido.get("mensagem") or "")
        if http == 500 and chave and chave.group(1).upper() == campo.upper():
            return ESTRUTURAL
        if http == 500:
            return ERRO
        return RECUSA
    classe = obtido["classe"]
    if not classe:
        # HTTP 200 com corpo `null`: a API nao devolve item nem erro. E o modo
        # de falha mais perigoso para quem consome -- o cliente le "sem
        # resultado" onde na verdade houve entrada invalida.
        return VAZIO
    if classe == base:
        return INERTE
    if (classe[0] or DESCONHECIDO).lower() == DESCONHECIDO:
        return TOTAL
    return PARCIAL


# ------------------------------------------------------------------------ saida

RANQUE = {ESTRUTURAL: 6, VAZIO: 5, TOTAL: 4, PARCIAL: 3, RECUSA: 2, ERRO: 1,
          INERTE: 0}


def imprimir_matriz(resultado, top=None):
    linhas = []
    for campo, dados in resultado.items():
        contagem = collections.Counter(v["sinal"] for v in dados["perfis"].values())
        peso = max([RANQUE[s] for s in contagem] or [0])
        fortes = sum(contagem[s] for s in (ESTRUTURAL, VAZIO, TOTAL, PARCIAL))
        linhas.append((peso, fortes, campo, dados, contagem))
    linhas.sort(key=lambda x: (-x[0], -x[1], x[2]))

    print("\n%-24s %6s %6s %6s %6s %6s %6s   %s"
          % ("CAMPO", "APLIC", "ESTRU", "VAZIO", "TOTAL", "PARC", "INER",
             "ORDENS AFETADAS"))
    print("-" * 110)
    for _, _, campo, dados, contagem in (linhas[:top] if top else linhas):
        afetadas = sorted({v["ordem"] for v in dados["perfis"].values()
                           if v["sinal"] in (ESTRUTURAL, VAZIO, TOTAL, PARCIAL)})
        resumo = ", ".join(o.title() for o in afetadas[:5])
        if len(afetadas) > 5:
            resumo += ", +%d" % (len(afetadas) - 5)
        print("%-24s %6d %6d %6d %6d %6d %6d   %s"
              % (campo, len(dados["perfis"]), contagem[ESTRUTURAL], contagem[VAZIO],
                 contagem[TOTAL], contagem[PARCIAL], contagem[INERTE], resumo or "-"))
    print("-" * 110)
    print("APLIC = perfis do painel em que o campo existia (a carga mudou de fato).")
    print("ESTRU = HTTP 500, chave lida sem guarda pelo motor Prolog.")
    print("VAZIO = HTTP 200 com corpo null: nem resultado, nem erro.")
    print("TOTAL = classificacao virou 'unknown'.  PARC = classe mudou.  INER = nada mudou.")


# ---------------------------------------------------------------------- comandos

def executar(args):
    todos, defeituosos = av.carregar_pykka7()
    painel = todos if args.todos else estratificar(todos, args.por_ordem)
    campos, presencas = universo_de_campos(todos)
    if args.campos:
        pedidos = [c.strip().upper() for c in args.campos.split(",") if c.strip()]
        fora = [c for c in pedidos if c not in campos]
        if fora:
            sys.stderr.write("[aviso] fora do universo do dataset: %s\n" % ", ".join(fora))
        campos = [c for c in pedidos if c in campos]

    ordens = collections.Counter((p.get("ORDEM") or DESCONHECIDO).upper() for p in painel)
    print("dataset ................. %d perfis (%d ilegiveis)" % (len(todos), len(defeituosos)))
    print("painel .................. %d perfis, %d ordens" % (len(painel), len(ordens)))
    print("campos na varredura ..... %d" % len(campos))
    print("modo de ablacao ......... %s" % args.modo)
    print("requisicoes (piso) ...... %d  (1 por campo + base, mais isolamento se falhar)"
          % (len(campos) + 1))

    if args.simular:
        print("\n--simular: nada foi enviado.")
        print("ordens no painel: %s" % ", ".join("%s(%d)" % (o.title(), n)
                                                 for o, n in ordens.most_common()))
        for campo in campos:
            print("  %-24s presente em %d horizontes" % (campo, presencas[campo]))
        return 0

    sessao = Sessao(credencial_de(args), args)

    sys.stderr.write("[api] linha de base (%d perfis)\n" % len(painel))
    resp_base = sondar(sessao, painel, "__base__")
    base = {pid: v["classe"] for pid, v in resp_base.items() if v["http"] == 200}
    quebrados = [pid for pid, v in resp_base.items() if v["http"] != 200]
    if not base:
        raise SystemExit("A linha de base nao retornou nada -- abortando.")
    if quebrados:
        print("\n[aviso] %d perfis ja falham intactos e saem do painel: %s"
              % (len(quebrados), ", ".join(quebrados)))
    painel = [p for p in painel if p.get("ID_PONTO") in base]

    ordem_por_id = {p["ID_PONTO"]: (p.get("ORDEM") or DESCONHECIDO).upper() for p in painel}
    print("linha de base ........... %d perfis classificados" % len(base))

    resultado = collections.OrderedDict()
    for n, campo in enumerate(campos, start=1):
        sondas = []
        for perfil in painel:
            modificado, mudou = ablacionar(perfil, campo, args.modo)
            if mudou:
                sondas.append(modificado)
        sys.stderr.write("[api] %d/%d %s (%d perfis)\n" % (n, len(campos), campo, len(sondas)))
        if not sondas:
            resultado[campo] = {"perfis": {}}
            continue
        try:
            obtidos = sondar(sessao, sondas, campo)
        except Exception as erro:  # nenhum campo derruba a varredura inteira
            sys.stderr.write("[erro] %s: %s\n" % (campo, erro))
            resultado[campo] = {"perfis": {}, "excecao": str(erro)}
            continue
        perfis_saida = {}
        for perfil in sondas:
            pid = perfil["ID_PONTO"]
            obtido = obtidos.get(pid)
            if obtido is None:
                continue
            sinal = categorizar(campo, base[pid], obtido)
            registro = {"sinal": sinal, "ordem": ordem_por_id[pid], "http": obtido["http"]}
            if sinal in (PARCIAL, TOTAL):
                registro["de"] = texto_classe(base[pid])
                registro["para"] = texto_classe(obtido["classe"])
                registro["nivel"] = nivel_divergente(base[pid], obtido["classe"])
                registro["colapso"] = (obtido["classe"][0] == "NEOSSOLO"
                                       and base[pid][0] != "NEOSSOLO")
            if sinal in (ESTRUTURAL, RECUSA, ERRO):
                registro["mensagem"] = (obtido.get("mensagem") or "")[:300]
            perfis_saida[pid] = registro
        resultado[campo] = {"perfis": perfis_saida}
        gravar(montar_relatorio(args, painel, sessao, base, resultado), args, quieto=True)

    imprimir_matriz(resultado, top=args.top)
    print("\nrequisicoes gastas ...... %d em %.0f s" % (sessao.requisicoes, sessao.tempo))

    gravar(montar_relatorio(args, painel, sessao, base, resultado), args)
    return 0


def montar_relatorio(args, painel, sessao, base, resultado):
    return {
        "tipo": "ablacao",
        "modo": args.modo,
        "painel": [p["ID_PONTO"] for p in painel],
        "requisicoes": sessao.requisicoes,
        "base": {k: list(v) for k, v in base.items()},
        "campos": resultado,
    }


def gravar(relatorio, args, quieto=False):
    """Grava a cada campo: uma queda no meio da varredura nao perde o andado."""
    if not args.saida:
        return
    with open(args.saida, "w", encoding="utf-8") as fh:
        json.dump(relatorio, fh, ensure_ascii=False, indent=2)
    if not quieto:
        print("relatorio gravado em %s" % args.saida)


def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--campos", help="lista separada por virgula; padrao: todos")
    p.add_argument("--modo", choices=("remover", "nulo"), default="remover",
                   help="remove a chave (padrao) ou atribui null")
    p.add_argument("--por-ordem", type=int, default=1,
                   help="perfis por ordem de solo no painel (padrao: 1)")
    p.add_argument("--todos", action="store_true",
                   help="usa os 94 perfis em vez do painel estratificado")
    p.add_argument("--manter-rotulos", action="store_true",
                   help="nao remove ORDEM/SUBORDEM/GDE_GRUPO/SUBGRUPO da entrada")
    p.add_argument("--lote", type=int, default=25, help="compatibilidade; nao usado")
    p.add_argument("--top", type=int, help="mostra so as N primeiras linhas da matriz")
    p.add_argument("--simular", action="store_true", help="plano e custo, sem rede")
    p.add_argument("--credenciais", help="JSON com consumer_key/consumer_secret")
    p.add_argument("--saida", help="grava o relatorio JSON neste caminho")
    p.add_argument("--pausa", type=float, default=0.0, help="segundos entre chamadas")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("-v", "--verboso", action="store_true")
    return executar(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(principal())
