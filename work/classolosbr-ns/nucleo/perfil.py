"""Modelo do perfil e do horizonte, e leitura do JSON do contrato.

O esquema seguido é o do contrato publicado da API SmartSolosExpert v1
(7 propriedades de perfil + 57 de horizonte) — o mesmo que os arquivos do
conjunto curado PYKKA7 usam, com quatro campos a mais de metadado de curadoria
e três caracteres booleanos que o contrato não declara.

⚠️ Um defeito conhecido do PYKKA7: `GeoTab_PE_001_Lagoa_dos_Gatos.json` traz
uma chave `}` sobrando no fim, o que quebra `json.load`. `carregar_json()` usa
`raw_decode`, que lê o primeiro objeto válido e ignora o resto.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Profundidade sentinela usada no acervo quando o horizonte não tem limite
# inferior determinado ("...+"). Aparece como 10000 em vários perfis.
INDETERMINADA = 10000.0


@dataclass
class Horizonte:
    """Um horizonte descrito. Atributos ausentes são `None`, nunca zero.

    A distinção importa: `None` propaga como indeterminado na avaliação, ao
    passo que zero é um valor medido. Confundi-los produziria refutação onde
    a norma não refuta.
    """

    simbolo: str
    limite_sup: float | None = None
    limite_inf: float | None = None
    atributos: dict[str, float | bool | str | None] = field(default_factory=dict)
    #: Profundidade até onde o horizonte aberto ("110-150+ cm") foi observado,
    #: lida na ficha quando o JSON grava só o sentinela 10000. Limite
    #: **mínimo**, nunca substitui `limite_inf`. Ver `espessura_minima`.
    limite_inf_observado: float | None = None

    def get(self, nome: str):
        return self.atributos.get(nome)

    @property
    def espessura(self) -> float | None:
        if self.limite_sup is None or self.limite_inf is None:
            return None
        if self.limite_inf >= INDETERMINADA:
            return None
        return self.limite_inf - self.limite_sup

    @property
    def espessura_minima(self) -> float | None:
        """Espessura que o horizonte certamente tem.

        A própria espessura, quando os dois limites são conhecidos; num
        horizonte aberto, a parte observada (`limite_inf_observado` menos o
        limite superior); senão `None`. Serve a critérios de espessura
        mínima: se a parte observada já basta, o critério está satisfeito,
        e se não basta, nada se pode concluir — o horizonte continua.
        """
        if self.espessura is not None:
            return self.espessura
        if self.limite_sup is not None and self.limite_inf_observado is not None:
            return self.limite_inf_observado - self.limite_sup
        return None

    def sobrepoe(self, topo: float, base: float) -> float:
        """Espessura da interseção com o intervalo [topo, base), em cm."""
        if self.limite_sup is None or self.limite_inf is None:
            return 0.0
        inf = min(self.limite_inf, INDETERMINADA)
        return max(0.0, min(inf, base) - max(self.limite_sup, topo))

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.simbolo}({self.limite_sup}-{self.limite_inf})"


@dataclass
class Perfil:
    """Sequência ordenada de horizontes, mais os atributos de perfil."""

    id_ponto: str
    horizontes: list[Horizonte] = field(default_factory=list)
    drenagem: int | None = None
    classe_registrada: tuple[str | None, str | None, str | None, str | None] = (
        None, None, None, None,
    )

    def __post_init__(self) -> None:
        self.horizontes.sort(
            key=lambda h: (h.limite_sup if h.limite_sup is not None else 1e9)
        )

    def abaixo_de(self, horizonte: Horizonte) -> Horizonte | None:
        """O horizonte imediatamente subjacente, ou None."""
        try:
            i = self.horizontes.index(horizonte)
        except ValueError:
            return None
        return self.horizontes[i + 1] if i + 1 < len(self.horizontes) else None

    def acima_de(self, horizonte: Horizonte) -> Horizonte | None:
        try:
            i = self.horizontes.index(horizonte)
        except ValueError:
            return None
        return self.horizontes[i - 1] if i > 0 else None

    def profundidade_maxima(self) -> float | None:
        fundos = [
            h.limite_inf for h in self.horizontes
            if h.limite_inf is not None and h.limite_inf < INDETERMINADA
        ]
        return max(fundos) if fundos else None


# ---------------------------------------------------------------- leitura ---

_CAMPOS_PERFIL = {"ID_PONTO", "DRENAGEM", "HORIZONTES",
                  "ORDEM", "SUBORDEM", "GDE_GRUPO", "SUBGRUPO"}


def _limites(simbolo: str, sup, inf):
    """Limites do horizonte, com o orgânico superficial posto acima do zero.

    🚨 Décimo nono defeito (2026-10-17), achado na comparação com a linha de
    base. Pela convenção de campo, o horizonte orgânico que recobre o solo
    mineral é medido **da superfície mineral para cima**: `O 3-0` é uma camada
    de 3 cm acima dela. Lidos literalmente, os limites invertidos punham o O
    entre o A (0-8) e o BA (8-20), o B latossólico deixava de estar
    "imediatamente abaixo do A", e o núcleo refutava a classe — 35 das
    discordâncias com o sistema de referência no acervo nacional, que nesses
    casos acertava. Agora o O ou H com limite inferior menor que o superior
    ocupa de −superior a −inferior (`O 3-0` → −3 a 0 cm).
    """
    letra = simbolo.lstrip("0123456789IVX ")[:1]
    if letra in ("O", "H") and None not in (sup, inf) and inf < sup:
        return -sup, -inf
    return sup, inf


def de_dicionario(bruto: dict) -> Perfil:
    """Constrói um `Perfil` a partir de um item no formato do contrato."""
    horizontes = []
    for h in bruto.get("HORIZONTES") or []:
        atributos = {
            k: v for k, v in h.items()
            if k not in {"SIMB_HORIZ", "LIMITE_SUP", "LIMITE_INF"}
        }
        simbolo = str(h.get("SIMB_HORIZ") or "")
        sup, inf = _limites(simbolo, _num(h.get("LIMITE_SUP")), _num(h.get("LIMITE_INF")))
        horizonte = Horizonte(
            simbolo=simbolo,
            limite_sup=sup,
            limite_inf=inf,
            atributos=atributos,
        )
        horizonte.atributos.update(_derivados(horizonte))
        horizontes.append(horizonte)
    return Perfil(
        id_ponto=str(bruto.get("ID_PONTO") or "sem-id"),
        horizontes=horizontes,
        drenagem=_num(bruto.get("DRENAGEM")),
        classe_registrada=(
            bruto.get("ORDEM"), bruto.get("SUBORDEM"),
            bruto.get("GDE_GRUPO"), bruto.get("SUBGRUPO"),
        ),
    )


def carregar_json(caminho: str | Path) -> list[Perfil]:
    """Lê um arquivo do contrato. Tolera lixo após o primeiro objeto válido."""
    texto = Path(caminho).read_text(encoding="utf-8")
    dados, _ = json.JSONDecoder().raw_decode(texto)
    itens = dados.get("items", dados if isinstance(dados, list) else [dados])
    perfis = [de_dicionario(i) for i in itens]
    for p in perfis:
        _aplicar_profundidade_observada(p)
    return perfis


#: Profundidades observadas dos horizontes abertos do PYKKA7, lidas nas fichas
#: em 2026-10-14 (décimo primeiro defeito). Ver o arquivo para a procedência.
_PROFUNDIDADES = Path(__file__).parent / "dados" / "pykka7_profundidade_observada.json"
_observadas: dict[tuple[str, float], float] | None = None


def _aplicar_profundidade_observada(perfil: Perfil) -> None:
    """Preenche `limite_inf_observado` nos horizontes abertos conhecidos."""
    global _observadas
    if _observadas is None:
        _observadas = {}
        if _PROFUNDIDADES.exists():
            for r in json.loads(_PROFUNDIDADES.read_text(encoding="utf-8"))["horizontes"]:
                if r.get("limite_inf_ficha") is not None:
                    _observadas[(r["id_ponto"], float(r["limite_sup"]))] = float(
                        r["limite_inf_ficha"])
    for h in perfil.horizontes:
        if (h.limite_inf is not None and h.limite_inf >= INDETERMINADA
                and h.limite_sup is not None):
            h.limite_inf_observado = _observadas.get((perfil.id_ponto, h.limite_sup))


def _derivados(h: Horizonte) -> dict:
    """Atributos que a norma usa e o contrato não traz prontos.

    São calculados aqui, e não dentro das regras, para que as regras
    permaneçam legíveis como transcrição da norma: `V_PERCENT >= 50` lê-se
    como o texto escreve ("saturação por bases alta"), ao passo que a fórmula
    embutida na regra a tornaria ilegível.

    * `SOMA_BASES` (S) = Ca + Mg + K + Na, em cmolc/kg
    * `CTC` (T) = S + H + Al
    * `V_PERCENT` = 100·S/T — saturação por bases
    * `ATIVIDADE_ARGILA` = 1000·T/argila, em cmolc/kg de argila; o limiar de
      27 separa argila de atividade alta (Ta) da baixa (Tb)
    * `ESPESSURA` — em cm, quando ambos os limites são conhecidos

    Qualquer parcela ausente propaga `None`: a lógica de três valores trata
    isso como indeterminado, e não como zero.
    """
    def v(nome):
        x = h.atributos.get(nome)
        return float(x) if isinstance(x, (int, float)) else None

    ca, mg, k, na = v("CA_TROC"), v("MG_TROC"), v("K_TROC"), v("NA_TROC")
    hidro, al, argila = v("H_TROC"), v("AL_TROC"), v("ARGILA")

    derivados: dict[str, float | None] = {"ESPESSURA": h.espessura}

    # Soma Ca + Mg (2026-10-16, decisão do usuário): quando o laudo registra só
    # a soma — 37,4% dos horizontes do BDSolos com dado de Ca/Mg —, ela basta
    # para S, T, V% e a atividade da argila, que não dependem da partição. O
    # adaptador a entrega como `_CA_MG_TROC`, fora do contrato da API. Ca e Mg
    # separados, quando existem, têm precedência; a soma nunca é repartida.
    ca_mg = ca + mg if None not in (ca, mg) else v("_CA_MG_TROC")
    if ca_mg is not None and None not in (k, na):
        soma = ca_mg + k + na
        derivados["SOMA_BASES"] = soma
        if None not in (hidro, al):
            ctc = soma + hidro + al
            derivados["CTC"] = ctc
            if ctc > 0:
                derivados["V_PERCENT"] = 100.0 * soma / ctc
            if argila and argila > 0:
                derivados["ATIVIDADE_ARGILA"] = 1000.0 * ctc / argila
    # V do boletim (2026-10-17, decisão do usuário, opção c). Sem os
    # componentes, vale o V informado no laudo (`_V_BOLETIM`, fora do
    # contrato; ver `tools/bdsolos_adapter.py`). Com os dois, vale o
    # calculado, e o informado só arbitra: se caem em lados opostos de um
    # limiar da norma, o avaliador examina as duas versões e devolve
    # indeterminado onde elas discordam (`avaliador._variantes_de_leitura`).
    if derivados.get("V_PERCENT") is None and v("_V_BOLETIM") is not None:
        derivados["V_PERCENT"] = v("_V_BOLETIM")
    derivados.update(_derivados_niveis(h, derivados))
    return derivados


#: Matiz Munsell como número, para "7,5YR ou mais amarelo" virar comparação:
#: R de 0 a 10, YR de 10 a 20, Y de 20 a 30. 2,5YR → 12,5; 5YR → 15;
#: 7,5YR → 17,5; 10YR → 20. Matizes de gleização (GY, G, BG, B, PB) e o
#: neutro (N) não têm posição nessa escala e ficam None.
_FAMILIAS_MATIZ = {"R": 0.0, "YR": 10.0, "Y": 20.0}


def matiz_numerico(matiz) -> float | None:
    if not isinstance(matiz, str):
        return None
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(YR|R|Y)\s*", matiz.upper())
    if not m:
        return None
    return _FAMILIAS_MATIZ[m.group(2)] + float(m.group(1).replace(",", "."))


def _derivados_niveis(h: Horizonte, base: dict) -> dict:
    """Caracteres por horizonte usados nos níveis 2 e 3 (SiBCS 5ª ed.).

    Sempre devolvem a chave — None quando falta parcela —, para que um
    recálculo depois de remover um atributo apague o valor antigo (ver
    `explicador.alterar` e `avaliacao_parcial.remover`). Os caracteres são
    1,0 (presente) ou 0,0 (ausente), para serem lidos por `Compara` com a
    agregação "maior parte".

    * `MATIZ_NUM` — ver `matiz_numerico`.
    * `ALUMINICO` — 5ª ed., Cap. 1, p. 32: "dessaturado e [...] alumínio
      extraível ≥ 4 cmolc kg-1, além de [...] saturação por alumínio ≥ 50%
      e/ou saturação por bases < 50%". ⚠️ "Dessaturado" já é V < 50%, e o
      "e/ou" torna a saturação por alumínio redundante: lido como Al ≥ 4 e
      V < 50%.
    * `ACRICO` — p. 32: (S + Al) ≤ 1,5 cmolc kg-1 de argila e (pH KCl ≥ 5,0
      ou ΔpH = pH KCl − pH H2O ≥ 0).
    * `SAT_NA` — 100·Na/T, em % (caráter sódico ≥ 15%, p. 39).
    * `CROMICO` — p. 34, cor úmida: (a) matiz ≤ 5YR, valor ≥ 3, croma ≥ 4;
      (b) matiz > 5YR até 10YR, valor ≥ 4, croma ≥ 4; (c) matiz > 10YR até
      5Y, valor ≥ 5, croma > 4.
    * `COR_BRUNO_ACINZENTADA` — Argissolos, p. 115: matiz ≥ 5YR (5YR ou
      mais amarelo), valor de 3 a 4, croma ≤ 4.
    * `COR_ACINZENTADA` — Argissolos, p. 116: matiz ≥ 7,5YR, valor ≥ 5,
      croma < 4.
    """
    def v(nome):
        x = h.atributos.get(nome)
        return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None

    matiz = matiz_numerico(h.atributos.get("COR_UMIDA_MATIZ"))
    valor, croma = v("COR_UMIDA_VALOR"), v("COR_UMIDA_CROMA")
    al, ph_kcl, ph_agua = v("AL_TROC"), v("PH_KCL"), v("PH_AGUA")
    argila, na = v("ARGILA"), v("NA_TROC")
    soma, ctc, v_pct = base.get("SOMA_BASES"), base.get("CTC"), base.get("V_PERCENT")

    def flag(cond):
        return None if cond is None else (1.0 if cond else 0.0)

    saida: dict[str, float | None] = {"MATIZ_NUM": matiz}
    saida["ALUMINICO"] = flag(None if None in (al, v_pct) else (al >= 4 and v_pct < 50))
    acrico = None
    if None not in (soma, al, argila) and argila > 0:
        baixa = (soma + al) * 1000.0 / argila <= 1.5
        if not baixa:
            acrico = False
        else:
            ph_ok = (ph_kcl is not None and ph_kcl >= 5.0) or \
                (None not in (ph_kcl, ph_agua) and ph_kcl - ph_agua >= 0)
            falta_ph = ph_kcl is None or (ph_kcl < 5.0 and ph_agua is None)
            acrico = True if ph_ok else (None if falta_ph else False)
    saida["ACRICO"] = flag(acrico)
    saida["SAT_NA"] = (100.0 * na / ctc) if None not in (na, ctc) and ctc > 0 else None
    cromico = None
    if None not in (matiz, valor, croma):
        if matiz <= 15:
            cromico = valor >= 3 and croma >= 4
        elif matiz <= 20:
            cromico = valor >= 4 and croma >= 4
        elif matiz <= 25:
            cromico = valor >= 5 and croma > 4
        else:
            cromico = False
    saida["CROMICO"] = flag(cromico)
    saida["COR_BRUNO_ACINZENTADA"] = flag(
        None if None in (matiz, valor, croma)
        else (matiz >= 15 and 3 <= valor <= 4 and croma <= 4))
    saida["COR_ACINZENTADA"] = flag(
        None if None in (matiz, valor, croma)
        else (matiz >= 17.5 and valor >= 5 and croma < 4))

    # 4º nível (subgrupos), 5ª ed.:
    # * SOLODICO — saturação por sódio de 6% a < 15% (p. 39);
    # * SALINO — CE de 4 a < 7 dS/m (p. 39);
    # * HIPOCARBONATICO — CaCO3 equivalente de 50 a < 150 g/kg (p. 33);
    # * EUTRICO — pH em água ≥ 5,7 e S ≥ 2,0 cmolc/kg (p. 35);
    # * ARENOSA — textura arenosa: areia − argila > 700 g/kg (p. 46,
    #   conferida no cabeçalho da página do PDF em 2026-10-16). Desde
    #   2026-10-16, `horizontes._arenoso` (1º nível) usa a mesma fórmula; antes,
    #   aproximava por areia ≥ 700 e argila ≤ 150 (decisão do usuário).
    sat_na = saida["SAT_NA"]
    saida["SOLODICO"] = flag(None if sat_na is None else 6 <= sat_na < 15)
    ce = v("COND_ELETR")
    saida["SALINO"] = flag(None if ce is None else 4 <= ce < 7)
    caco3 = v("EQUI_CACO3")
    saida["HIPOCARBONATICO"] = flag(None if caco3 is None else 50 <= caco3 < 150)
    saida["EUTRICO"] = flag(None if None in (ph_agua, soma) else (ph_agua >= 5.7 and soma >= 2.0))
    ag, af = v("AREIA_GROS"), v("AREIA_FINA")
    saida["ARENOSA"] = flag(None if None in (ag, af, argila) else (ag + af - argila) > 700)
    return saida


def _num(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None
