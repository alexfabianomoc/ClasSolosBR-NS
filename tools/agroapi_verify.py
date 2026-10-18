#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cliente da API SmartSolosExpert (plataforma AgroAPI / Embrapa).

Roda perfis de solo contra o sistema especialista da Embrapa e apura a
concordancia por nivel categorico do SiBCS (metrica L0-L4 do recurso
/verification). Somente biblioteca padrao do Python 3 -- mesma restricao de
tools/search.py.

CREDENCIAIS (nunca passar por linha de comando -- ficam no historico do shell):

    Opcao A -- token ja gerado na Loja de APIs:
        export AGROAPI_TOKEN="eyJ4NXQi..."

    Opcao B -- chave e segredo da aplicacao (o script obtem e renova o token):
        export AGROAPI_CONSUMER_KEY="..."
        export AGROAPI_CONSUMER_SECRET="..."

    Como obter: Loja de APIs -> APPLICATIONS -> sua aplicacao -> aba
    Production Keys -> Generate keys. Ver wiki/sources/agroapi-primeiros-passos.md.
    O token expira em 3600 s; com a opcao B a renovacao e automatica.

USO:

    python tools/agroapi_verify.py --simular            # sem rede: monta e confere os lotes
    python tools/agroapi_verify.py --saude              # GET /health
    python tools/agroapi_verify.py                      # POST /verification sobre o PYKKA7
    python tools/agroapi_verify.py --classificar        # POST /classification (ignora rotulo)
    python tools/agroapi_verify.py --sonda-contrato     # campos nao declarados mudam a resposta?
    python tools/agroapi_verify.py --bdsolos            # linha de base independente (BDSolos)
    python tools/agroapi_verify.py --bdsolos --estratificar 20   # conjunto balanceado
    python tools/agroapi_verify.py --saida relatorio.json

AVISO METODOLOGICO -- leia antes de citar os numeros:
    Os 94 perfis do PYKKA7 carregam a classificacao **ja curada**, e a curadoria
    foi feita com o proprio SmartSolos. Rodar /verification sobre eles compara o
    sistema com um rotulo que ele ajudou a produzir: espera-se L4 quase total, e
    isso NAO e medida de acuracia. Serve como teste de conformidade (pipeline,
    contrato, autenticacao) e como deteccao de perfis anomalos.

    Para a linha de base INDEPENDENTE use --bdsolos: os rotulos do BDSolos vem
    de levantamentos pedologicos da Embrapa Solos, nao do SmartSolos. Ver
    wiki/outputs/adaptador-bdsolos-para-api.md.
"""

import argparse
import base64
import collections
import glob
import http.client
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_PYKKA7 = os.path.join(RAIZ, "raw", "pykka7-smartsolos-dataset")

URL_BASE = "https://api.cnptia.embrapa.br/smartsolos/expert/v1"
URL_TOKEN = "https://api.cnptia.embrapa.br/token"

# Metadados do dataset PYKKA7 que nao fazem parte do contrato de entrada da API.
CAMPOS_METADADOS = ("CURADORIA", "AUTOR_CURADORIA", "CURADORIA_AUTOR", "OBSERVACOES")

# Campos usados pelo dataset e ausentes do Swagger publicado. A sonda de contrato
# testa se a API os leva em conta ou apenas os ignora.
CAMPOS_NAO_DECLARADOS = ("FRAGMENTARIO", "LITOPLINTICO", "PETROPLINTICO", "TEOR_P")

NIVEIS = ("L0", "L1", "L2", "L3", "L4")
ROTULO_NIVEL = {
    "L0": "discorda ja na ordem",
    "L1": "concorda so na ordem",
    "L2": "concorda ate a subordem",
    "L3": "concorda ate o grande grupo",
    "L4": "concorda nos quatro niveis",
}


# ---------------------------------------------------------------- autenticacao

class Credencial(object):
    """Guarda o token e o renova quando falta pouco para expirar."""

    def __init__(self, token=None, chave=None, segredo=None, url_token=URL_TOKEN,
                 timeout=60, verboso=False):
        self._token = token
        self._chave = chave
        self._segredo = segredo
        self._url_token = url_token
        self._timeout = timeout
        self._verboso = verboso
        # Token informado direto pelo ambiente: nao sabemos quando expira.
        self._expira_em = float("inf") if token else 0.0

    @classmethod
    def do_ambiente(cls, url_token=URL_TOKEN, timeout=60, verboso=False):
        token = os.environ.get("AGROAPI_TOKEN")
        chave = os.environ.get("AGROAPI_CONSUMER_KEY")
        segredo = os.environ.get("AGROAPI_CONSUMER_SECRET")
        if not token and not (chave and segredo):
            raise SystemExit(
                "Credenciais ausentes. Defina AGROAPI_TOKEN, ou o par\n"
                "AGROAPI_CONSUMER_KEY + AGROAPI_CONSUMER_SECRET.\n"
                "Use --simular para montar os lotes sem chamar a API."
            )
        return cls(token, chave, segredo, url_token, timeout, verboso)

    @property
    def renovavel(self):
        return bool(self._chave and self._segredo)

    def token(self, forcar=False):
        if forcar or time.time() >= self._expira_em - 60:
            if self.renovavel:
                self._renovar()
            elif forcar:
                raise SystemExit(
                    "Token recusado (401) e nao ha AGROAPI_CONSUMER_KEY/SECRET para\n"
                    "renova-lo. Gere um token novo na Loja de APIs ou exporte o par."
                )
        return self._token

    def _renovar(self):
        basico = base64.b64encode(
            ("%s:%s" % (self._chave, self._segredo)).encode("utf-8")
        ).decode("ascii")
        corpo = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        req = urllib.request.Request(
            self._url_token,
            data=corpo,
            headers={
                "Authorization": "Basic " + basico,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", "replace")[:400]
            raise SystemExit(
                "Falha ao obter o token (HTTP %s) em %s\n%s\n"
                "Confira a chave e o segredo, e se o endpoint de token e esse mesmo\n"
                "(a aba Production Keys da Loja mostra o comando correto; use --url-token\n"
                "para apontar outro)." % (erro.code, self._url_token, detalhe)
            )
        self._token = dados["access_token"]
        self._expira_em = time.time() + float(dados.get("expires_in", 3600))
        if self._verboso:
            sys.stderr.write("[auth] token renovado, validade %s s\n"
                             % dados.get("expires_in", "?"))


# ------------------------------------------------------------------- transporte

def chamar(caminho, credencial, carga=None, metodo="POST", timeout=120,
           tentativas=4, verboso=False):
    """Chama um recurso da API. Renova o token uma vez em caso de 401."""
    url = URL_BASE + caminho
    corpo = json.dumps(carga, ensure_ascii=False).encode("utf-8") if carga is not None else None
    espera = 2.0
    renovou = False

    for tentativa in range(1, tentativas + 1):
        req = urllib.request.Request(
            url,
            data=corpo,
            headers={
                "Authorization": "Bearer " + credencial.token(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=metodo,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                bruto = resp.read().decode("utf-8")
                if not bruto.strip():
                    return resp.status, None
                try:
                    return resp.status, json.loads(bruto)
                except ValueError:
                    # Observado em producao: 200 com corpo JSON malformado.
                    # raw_decode recupera o primeiro objeto; se nem isso der,
                    # devolvemos o corpo cru para quem chamou decidir.
                    try:
                        return resp.status, json.JSONDecoder().raw_decode(bruto.strip())[0]
                    except ValueError:
                        return resp.status, {"_corpo_ilegivel": bruto[:2000]}
        except urllib.error.HTTPError as erro:
            detalhe = erro.read().decode("utf-8", "replace")[:500]
            if erro.code == 401 and not renovou and credencial.renovavel:
                if verboso:
                    sys.stderr.write("[auth] 401 -- renovando token\n")
                credencial.token(forcar=True)
                renovou = True
                continue
            if erro.code in (429, 500, 502, 503, 504) and tentativa < tentativas:
                if verboso:
                    sys.stderr.write("[rede] HTTP %s -- nova tentativa em %.0fs\n"
                                     % (erro.code, espera))
                time.sleep(espera)
                espera *= 2
                continue
            return erro.code, {"erro": detalhe}
        except (urllib.error.URLError, http.client.IncompleteRead,
                ConnectionError, socket.timeout) as erro:
            # IncompleteRead: o gateway corta o corpo no meio. Acontece em
            # producao e antes derrubava a execucao inteira; agora e falha de
            # transporte como qualquer outra -- quem chama decide o que fazer.
            if tentativa < tentativas:
                if verboso:
                    sys.stderr.write("[rede] %s -- nova tentativa em %.0fs\n" % (erro, espera))
                time.sleep(espera)
                espera *= 2
                continue
            return None, {"erro": "falha de transporte: %s" % erro}
    return None, None


# ---------------------------------------------------------------------- entrada

def _decodificar(texto):
    """Le o primeiro objeto JSON e ignora lixo depois dele.

    Um dos 94 arquivos do PYKKA7 tem uma chave a mais no fim (defeito ja
    registrado em wiki/sources/pykka7-smartsolos-dataset.md); json.load falha,
    raw_decode nao.
    """
    return json.JSONDecoder().raw_decode(texto.strip())[0]


def carregar_pykka7(diretorio=DIR_PYKKA7):
    """Devolve os 94 perfis individuais. Ignora os agregados *_all.json."""
    if not os.path.isdir(diretorio):
        raise SystemExit("Dataset PYKKA7 nao encontrado em %s" % diretorio)
    arquivos = sorted(
        f for f in glob.glob(os.path.join(diretorio, "*", "json", "*.json"))
        if not os.path.basename(f).endswith("_all.json")
    )
    perfis, defeituosos = [], []
    for caminho in arquivos:
        try:
            dados = _decodificar(open(caminho, encoding="utf-8").read())
        except ValueError as erro:
            defeituosos.append((os.path.basename(caminho), str(erro)))
            continue
        for perfil in dados.get("items", [dados]):
            perfil.setdefault("_arquivo", os.path.basename(caminho))
            perfis.append(perfil)
    return perfis, defeituosos


def carregar_arquivo(caminho):
    dados = _decodificar(open(caminho, encoding="utf-8").read())
    return list(dados.get("items", [dados])), []


def carregar_bdsolos(nivel_minimo=4, ordem=None, estratificar=None):
    """Converte o CSV do BDSolos na hora, via tools/bdsolos_adapter.py.

    Rotulo independente do SmartSolos -- e esta, e nao o PYKKA7, a linha de
    base honesta. Ver o aviso metodologico no topo deste arquivo.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import bdsolos_adapter
    except ImportError:
        raise SystemExit("tools/bdsolos_adapter.py nao encontrado.")
    perfis, _ = bdsolos_adapter.ler_perfis()
    perfis = bdsolos_adapter.filtrar(perfis, nivel_minimo, ordem)
    if estratificar:
        perfis = bdsolos_adapter.estratificar(perfis, estratificar)
    return perfis, []


def limpar(perfil, manter_metadados=False, remover_nao_declarados=False):
    """Monta o perfil no formato aceito pela API."""
    limpo = {}
    for chave, valor in perfil.items():
        if chave.startswith("_"):
            continue
        if not manter_metadados and chave in CAMPOS_METADADOS:
            continue
        if chave == "HORIZONTES":
            limpo[chave] = [
                {k: v for k, v in h.items()
                 if not k.startswith("_")  # campos fora do contrato (ex.: _CA_MG_TROC)
                 and not (remover_nao_declarados and k in CAMPOS_NAO_DECLARADOS)}
                for h in (valor or [])
            ]
        else:
            limpo[chave] = valor
    return limpo


def em_lotes(sequencia, tamanho):
    for i in range(0, len(sequencia), tamanho):
        yield sequencia[i:i + tamanho]


# ----------------------------------------------------------------------- apuracao

def apurar(perfis, resultados):
    """Cruza a saida do /verification com os rotulos enviados.

    A API devolve `summary` agregado por lote; aqui reconstruimos tambem o nivel
    de concordancia perfil a perfil, para poder listar os divergentes.
    """
    por_id_bd = {r.get("ID_PONTO"): r for r in resultados.get("items_bd", [])}
    linhas = []
    for inferido in resultados.get("items", []):
        pid = inferido.get("ID_PONTO")
        referencia = por_id_bd.get(pid, {})
        nivel = 0
        for ordem, campo in enumerate(("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO"), start=1):
            a = (inferido.get(campo) or "").strip().upper()
            b = (referencia.get(campo) or "").strip().upper()
            if a and a == b:
                nivel = ordem
            else:
                break
        linhas.append({
            "ID_PONTO": pid,
            "nivel": "L%d" % nivel,
            "inferido": [inferido.get(c) for c in ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")],
            "referencia": [referencia.get(c) for c in ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")],
        })
    return linhas


def imprimir_resumo(total_api, linhas, enviados):
    print()
    print("=" * 68)
    print("CONCORDANCIA POR NIVEL CATEGORICO (metrica L0-L4 do /verification)")
    print("=" * 68)
    print("perfis enviados: %d | perfis com resposta: %d" % (enviados, len(linhas)))
    print()
    soma = sum(total_api.get(n, 0) for n in NIVEIS) or 1
    for n in NIVEIS:
        q = total_api.get(n, 0)
        barra = "#" * int(round(40.0 * q / soma))
        print("  %s  %5d  %5.1f%%  %-40s %s" % (n, q, 100.0 * q / soma, barra, ROTULO_NIVEL[n]))
    print()
    exatos = total_api.get("L4", 0)
    print("  concordancia plena (L4): %.1f%%" % (100.0 * exatos / soma))
    print("  divergencia na ordem (L0): %d perfil(is)" % total_api.get("L0", 0))

    divergentes = [l for l in linhas if l["nivel"] != "L4"]
    if divergentes:
        print()
        print("PERFIS DIVERGENTES (%d)" % len(divergentes))
        print("-" * 68)
        for l in divergentes[:40]:
            print("  [%s] %s" % (l["nivel"], l["ID_PONTO"]))
            print("        inferido:   %s" % " / ".join(str(x) for x in l["inferido"]))
            print("        referencia: %s" % " / ".join(str(x) for x in l["referencia"]))
        if len(divergentes) > 40:
            print("  ... e mais %d." % (len(divergentes) - 40))
    print()
    print("LEMBRETE: o rotulo do PYKKA7 foi produzido com o proprio SmartSolos.")
    print("Isto e teste de conformidade, nao medida de acuracia independente.")


# --------------------------------------------------------------------- comandos

def cmd_saude(credencial, args):
    codigo, _ = chamar("/health", credencial, metodo="GET",
                       timeout=args.timeout, verboso=args.verboso)
    print("GET /health -> HTTP %s%s" % (codigo, "  (ok)" if codigo in (200, 204) else ""))
    return 0 if codigo in (200, 204) else 1


def cmd_sonda_contrato(credencial, perfis, args):
    """Os campos usados pelo dataset e ausentes do Swagger mudam a resposta?

    Escolhe um perfil que os utilize, classifica com e sem eles e compara.
    Resolve a sinalizacao registrada em wiki/concepts/esquema-de-dados-de-perfil-de-solo.md.
    """
    alvo = None
    for perfil in perfis:
        for h in (perfil.get("HORIZONTES") or []):
            if any(c in h for c in CAMPOS_NAO_DECLARADOS):
                alvo = perfil
                break
        if alvo:
            break
    if alvo is None:
        print("Nenhum perfil usa %s -- sonda inaplicavel." % ", ".join(CAMPOS_NAO_DECLARADOS))
        return 1

    print("Perfil de teste: %s" % alvo.get("ID_PONTO"))
    usados = sorted({c for h in (alvo.get("HORIZONTES") or [])
                     for c in CAMPOS_NAO_DECLARADOS if c in h})
    print("Campos nao declarados presentes: %s" % ", ".join(usados))

    com = {"items": [limpar(alvo)]}
    sem = {"items": [limpar(alvo, remover_nao_declarados=True)]}
    cod_a, resp_a = chamar("/classification", credencial, com,
                           timeout=args.timeout, verboso=args.verboso)
    cod_b, resp_b = chamar("/classification", credencial, sem,
                           timeout=args.timeout, verboso=args.verboso)

    def classe(resp):
        try:
            it = resp["items"][0]
            return " / ".join(str(it.get(c)) for c in ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO"))
        except Exception:
            return "(sem resposta utilizavel: %r)" % resp

    print()
    print("  com os campos (HTTP %s): %s" % (cod_a, classe(resp_a)))
    print("  sem os campos (HTTP %s): %s" % (cod_b, classe(resp_b)))
    print()
    if cod_a != 200:
        print("=> A API RECUSOU a carga com os campos nao declarados.")
        print("   O contrato publicado e restritivo: filtrar antes de enviar.")
    elif classe(resp_a) != classe(resp_b):
        print("=> Os campos MUDAM a classificacao: sao lidos pelo motor e o")
        print("   Swagger publicado esta DEFASADO em relacao a implementacao.")
    else:
        print("=> A resposta nao muda. Ou os campos sao ignorados, ou este perfil")
        print("   nao depende deles. Repita com outros perfis antes de concluir.")
    return 0


def cmd_verificar(credencial, perfis, args):
    caminho = "/classification" if args.classificar else "/verification"
    total = collections.Counter()
    linhas, falhas = [], []
    enviados = 0

    lotes = list(em_lotes(perfis, args.lote))
    for i, lote in enumerate(lotes, start=1):
        carga = {"items": [limpar(p, manter_metadados=args.metadados) for p in lote]}
        if args.verboso:
            sys.stderr.write("[api] lote %d/%d (%d perfis)\n" % (i, len(lotes), len(lote)))
        codigo, resposta = chamar(caminho, credencial, carga,
                                  timeout=args.timeout, verboso=args.verboso)
        if codigo != 200 or not isinstance(resposta, dict):
            falhas.append({"lote": i, "http": codigo, "resposta": resposta,
                           "ids": [p.get("ID_PONTO") for p in lote]})
            sys.stderr.write("[api] lote %d falhou: HTTP %s\n" % (i, codigo))
            continue
        enviados += len(lote)
        if args.classificar:
            for item in resposta.get("items", []):
                linhas.append({"ID_PONTO": item.get("ID_PONTO"),
                               "inferido": [item.get(c) for c in
                                            ("ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO")]})
        else:
            total.update({k: v for k, v in (resposta.get("summary") or {}).items() if k in NIVEIS})
            linhas.extend(apurar(lote, resposta))
        if args.pausa:
            time.sleep(args.pausa)

    if args.classificar:
        print("\n%d perfis classificados via /classification." % len(linhas))
        for l in linhas[:20]:
            print("  %-42s %s" % (l["ID_PONTO"], " / ".join(str(x) for x in l["inferido"])))
        if len(linhas) > 20:
            print("  ... e mais %d." % (len(linhas) - 20))
    else:
        imprimir_resumo(total, linhas, enviados)

    if falhas:
        print("\n%d lote(s) falharam -- ver o relatorio para os detalhes." % len(falhas))

    if args.saida:
        relatorio = {
            "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "recurso": caminho,
            "url_base": URL_BASE,
            "perfis_enviados": enviados,
            "tamanho_do_lote": args.lote,
            "summary_agregado": dict(total),
            "resultados": linhas,
            "falhas": falhas,
            "aviso": ("Rotulos do PYKKA7 sao pos-curadoria feita com o proprio "
                      "SmartSolos: conformidade, nao acuracia independente."),
        }
        with open(args.saida, "w", encoding="utf-8") as fp:
            json.dump(relatorio, fp, ensure_ascii=False, indent=2)
        print("Relatorio salvo em %s" % args.saida)
    return 1 if falhas else 0


def cmd_simular(perfis, defeituosos, args):
    lotes = list(em_lotes(perfis, args.lote))
    cargas = [{"items": [limpar(p, manter_metadados=args.metadados) for p in lote]}
              for lote in lotes]
    bytes_totais = sum(len(json.dumps(c, ensure_ascii=False).encode("utf-8")) for c in cargas)

    horizontes = sum(len(p.get("HORIZONTES") or []) for p in perfis)
    sem_rotulo = [p.get("ID_PONTO") for p in perfis if not p.get("ORDEM")]
    ordens = collections.Counter((p.get("ORDEM") or "(vazio)") for p in perfis)

    print("SIMULACAO -- nada foi enviado a rede.")
    print("-" * 68)
    print("perfis carregados ....... %d" % len(perfis))
    print("horizontes .............. %d (media %.2f por perfil)"
          % (horizontes, horizontes / float(len(perfis) or 1)))
    print("lotes de %-3d ............ %d requisicoes" % (args.lote, len(lotes)))
    print("carga total ............. %.1f KB" % (bytes_totais / 1024.0))
    print("cota mensal do tier ..... 100000 requisicoes (Gratuito100KPorMes)")
    print("consumo desta execucao .. %.3f%% da cota" % (100.0 * len(lotes) / 100000))
    if defeituosos:
        print("arquivos ilegiveis ...... %d" % len(defeituosos))
        for nome, erro in defeituosos:
            print("    %s: %s" % (nome, erro))
    if sem_rotulo:
        print("sem rotulo de referencia  %d (inuteis para /verification): %s"
              % (len(sem_rotulo), ", ".join(str(x) for x in sem_rotulo[:5])))
    print()
    print("distribuicao por ordem (rotulo de referencia enviado):")
    for ordem, q in ordens.most_common():
        print("    %-22s %3d" % (ordem, q))
    print()
    exemplo = json.dumps(cargas[0]["items"][0], ensure_ascii=False, indent=2)
    print("primeiro perfil da primeira carga (truncado):")
    print("\n".join(exemplo.splitlines()[:24]))
    print("    ...")
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as fp:
            json.dump(cargas, fp, ensure_ascii=False, indent=2)
        print("\nCargas gravadas em %s" % args.saida)
    return 0


# -------------------------------------------------------------------------- cli

def principal(argv=None):
    p = argparse.ArgumentParser(
        description="Roda perfis de solo contra a API SmartSolosExpert da AgroAPI.",
        epilog="Credenciais vem do ambiente: AGROAPI_TOKEN, ou "
               "AGROAPI_CONSUMER_KEY + AGROAPI_CONSUMER_SECRET.",
    )
    p.add_argument("--arquivo", help="JSON no formato da API; padrao: dataset PYKKA7 completo")
    p.add_argument("--bdsolos", action="store_true",
                   help="usa o BDSolos convertido na hora (rotulo independente) "
                        "em vez do PYKKA7")
    p.add_argument("--nivel-minimo", type=int, choices=(1, 2, 3, 4), default=4,
                   help="com --bdsolos: so perfis rotulados ate este nivel (padrao: 4)")
    p.add_argument("--ordem", help="com --bdsolos: filtra por uma ordem (ex.: LATOSSOLO)")
    p.add_argument("--estratificar", type=int, metavar="N",
                   help="com --bdsolos: amostra ate N perfis por ordem")
    p.add_argument("--lote", type=int, default=25, help="perfis por requisicao (padrao: 25)")
    p.add_argument("--limite", type=int, help="usa apenas os N primeiros perfis")
    p.add_argument("--classificar", action="store_true",
                   help="usa /classification (ignora o rotulo) em vez de /verification")
    p.add_argument("--saude", action="store_true", help="apenas GET /health")
    p.add_argument("--sonda-contrato", action="store_true",
                   help="testa se os campos ausentes do Swagger mudam a resposta")
    p.add_argument("--simular", action="store_true",
                   help="monta os lotes e relata, sem chamar a API nem exigir credencial")
    p.add_argument("--metadados", action="store_true",
                   help="nao remove CURADORIA/OBSERVACOES da carga (para testar o contrato)")
    p.add_argument("--saida", help="grava o relatorio JSON neste caminho")
    p.add_argument("--pausa", type=float, default=0.0, help="segundos entre lotes")
    p.add_argument("--timeout", type=int, default=120, help="timeout por requisicao (s)")
    p.add_argument("--url-token", default=URL_TOKEN, help="endpoint OAuth2 (padrao: %s)" % URL_TOKEN)
    p.add_argument("-v", "--verboso", action="store_true")
    args = p.parse_args(argv)

    if args.saude and not args.simular:
        return cmd_saude(Credencial.do_ambiente(args.url_token, args.timeout, args.verboso), args)

    if args.bdsolos:
        perfis, defeituosos = carregar_bdsolos(args.nivel_minimo, args.ordem,
                                               args.estratificar)
    elif args.arquivo:
        perfis, defeituosos = carregar_arquivo(args.arquivo)
    else:
        perfis, defeituosos = carregar_pykka7()
    if args.limite:
        perfis = perfis[:args.limite]
    if not perfis:
        raise SystemExit("Nenhum perfil carregado.")

    if args.simular:
        return cmd_simular(perfis, defeituosos, args)

    credencial = Credencial.do_ambiente(args.url_token, args.timeout, args.verboso)
    if args.sonda_contrato:
        return cmd_sonda_contrato(credencial, perfis, args)
    return cmd_verificar(credencial, perfis, args)


if __name__ == "__main__":
    sys.exit(principal())
