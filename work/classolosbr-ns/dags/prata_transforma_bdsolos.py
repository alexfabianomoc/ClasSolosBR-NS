"""Prata — tipagem, normalização de grão e rejeição explícita do BDSolos.

A Bronze preserva o CSV como texto, uma linha por horizonte, com as colunas de
perfil repetidas. A Prata faz três coisas que a Bronze deliberadamente não fez:

1. **Separa os dois grãos.** `perfis` (8.923, um por perfil) e `horizontes`
   (33.327, um por horizonte descrito) viram tabelas distintas. Manter tudo
   numa tabela só faz qualquer contagem de perfil exigir DISTINCT e convida ao
   erro de contar horizonte como se fosse perfil.
2. **Tipa, e rejeita o que não converte** — com motivo registrado, nunca em
   silêncio.
3. **Sinaliza, não filtra.** Perfil sem horizonte e perfil sem coordenada
   continuam na tabela, marcados por flag. Quem consome decide se exclui.

🚨 **Exceção: registro partido na origem** (achado de 2026-10-14). Em três
horizontes do perfil 797|12743|RS-142, o campo de material de origem traz
aspas internas sem escape (`"Arenitos da formação "Camaquã".`), e o leitor
parte cada registro em dois: uma metade truncada (16 colunas) e outra com as
colunas deslocadas, cujo `codigo_trabalho` é o texto `;";Campo natural."`.
Lidas como estão, as metades formam um **perfil que não existe**, com valores
fora de lugar. Isso não é dado a sinalizar: é registro que não se lê. Os seis
vão para `_rejeitados` com motivo e saem dos dois grãos; o perfil real, sem
nenhum registro legível, é contado à parte (`perfis_descartados_corrompidos`).
A Bronze continua preservando os seis como vieram.

⚠️ Números de referência medidos contra o arquivo real em 2026-08-31, não
estimados. Divergência na validação significa que a fonte ou o parsing mudou.

⚠️ Imports pesados ficam dentro das tasks: o scheduler reinterpreta este
arquivo a cada 30 s.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException

BUCKET_BRONZE = os.environ.get("S3_BUCKET_BRONZE", "bronze")
BUCKET_SILVER = os.environ.get("S3_BUCKET_SILVER", "silver")

ORIGEM_BRONZE = f"s3a://{BUCKET_BRONZE}/bdsolos/"
DESTINO_PERFIS = f"s3a://{BUCKET_SILVER}/perfis/"
DESTINO_HORIZONTES = f"s3a://{BUCKET_SILVER}/horizontes/"
DESTINO_REJEITADOS = f"s3a://{BUCKET_SILVER}/_rejeitados/"
# Achados do Sentinela sobre os símbolos de horizonte. Tabela SEPARADA de
# `horizontes` de propósito: sinaliza, não filtra, e não altera o grão.
DESTINO_ACHADOS = f"s3a://{BUCKET_SILVER}/achados_simbolo/"

# Edição da norma contra a qual validar os símbolos.
# ⚠️ "2015" é a 7ª edição do Manual de descrição e coleta de solo no campo.
# Existe uma 8ª (SBCS, 2025, 156 p.) ainda ausente do acervo — ver a página
# [[nomenclatura-de-horizontes-e-camadas]]. Ler como "conforme a 7ª edição",
# não como "conforme a norma vigente".
EDICAO_NORMA = os.environ.get("CLASSOLOSBR_EDICAO_NORMA", "2015")

CHAVE_PERFIL = ["codigo_trabalho", "codigo_pa", "numero_pa"]

# As 13 ordens do SiBCS **como aparecem no BDSolos**: singular e maiúsculo.
# ⚠️ Não é "Latossolos"/"Argissolos" — verificado contra a coluna
# `Classe de Solos Nível 1` do CSV, que traz ARGISSOLO, LATOSSOLO, etc.
ORDENS_SIBCS = [
    "ARGISSOLO", "CAMBISSOLO", "CHERNOSSOLO", "ESPODOSSOLO", "GLEISSOLO",
    "LATOSSOLO", "LUVISSOLO", "NEOSSOLO", "NITOSSOLO", "ORGANOSSOLO",
    "PLANOSSOLO", "PLINTOSSOLO", "VERTISSOLO",
]

HEMISFERIOS_LAT = ["Norte", "Sul"]
HEMISFERIOS_LON = ["Leste", "Oeste"]

# Valores medidos em 2026-08-31 (ver docstring).
# Revistos em 2026-10-14: 8.925 e 752 contavam o perfil fantasma e o RS-142.
ESPERADO = {
    "linhas_bronze": 34108,
    "registros_partidos": 6,
    "perfis": 8923,
    "perfis_descartados_corrompidos": 1,
    "horizontes": 33327,
    "perfis_sem_horizonte": 750,
    "perfis_com_horizonte": 8173,
}

# Limites do território brasileiro, para sanidade de coordenada.
BRASIL_LAT = (-33.75, 5.27)
BRASIL_LON = (-73.99, -34.79)


def _sufixos_de(simbolo: str) -> list[str]:
    """Sufixos de um símbolo, ou lista vazia se ele não for analisável."""
    from sentinela.gramatica_sufixos import analisa

    return analisa(simbolo).sufixos


def _sessao_spark(nome_app: str):
    """SparkSession local com Delta e acesso ao MinIO. Ver o DAG da Bronze."""
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    construtor = (
        SparkSession.builder.appName(nome_app)
        .master(os.environ.get("SPARK_MASTER_URL") or "local[*]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["S3_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["S3_SECRET_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
    )
    return configure_spark_with_delta_pip(
        construtor, extra_packages=["org.apache.hadoop:hadoop-aws:3.3.4"]
    ).getOrCreate()


#: Letras acentuadas do português e suas formas sem acento, para `translate`.
_ACENTUADAS = "áàâãäéèêëíìîïóòôõöúùûüç"
_SEM_ACENTO = "aaaaaeeeeiiiiooooouuuuc"


def _classificacao_comparavel(coluna: str):
    """Forma de comparação de uma classificação: o conteúdo, não a grafia.

    🚨 Até 2026-09-18 `foi_reclassificado` comparava as duas classificações
    **byte a byte**, e contava como reclassificação 81 perfis em que o texto
    só muda de forma — 69 apenas na caixa (`Latossolo Vermelho-Amarelo` ×
    `LATOSSOLO VERMELHO-AMARELO`), os outros em espaço, ponto final ou
    acento. A contagem saía 3.999; comparando conteúdo, sai **3.918**.
    Normaliza-se espaço, ponto final, caixa e acento — e nada além disso: um
    termo, um nível ou um qualificativo diferente continua sendo diferença.
    """
    texto = F.regexp_replace(F.trim(F.col(coluna)), r"\s+", " ")
    texto = F.regexp_replace(texto, r"[.\s]+$", "")
    return F.translate(F.lower(texto), _ACENTUADAS, _SEM_ACENTO)


def _texto(coluna: str):
    """Normaliza texto: apara espaços e transforma string vazia em NULL.

    No CSV, ausência é string vazia; em Prata, ausência tem que ser NULL, senão
    toda contagem de completude mente.
    """
    from pyspark.sql import functions as F

    limpo = F.trim(F.col(coluna))
    return F.when(limpo == "", None).otherwise(limpo)


def _numero(coluna: str, tipo):
    """Converte para número. Separador decimal do BDSolos é PONTO (verificado).

    ⚠️ `cast` do Spark devolve NULL quando falha — não levanta exceção. Por isso
    a rejeição se detecta comparando o convertido com o original, e não com
    try/except.
    """
    from pyspark.sql import functions as F

    return F.trim(F.col(coluna)).cast(tipo)


def _preenchido(coluna: str):
    """True quando a coluna da Bronze tem conteúdo de fato.

    Na Bronze a ausência pode chegar como NULL **ou** como string vazia,
    dependendo de o campo vir aspeado ou não no CSV. Tratar só um dos dois
    silencia metade dos casos.
    """
    from pyspark.sql import functions as F

    return F.col(coluna).isNotNull() & (F.trim(F.col(coluna)) != "")


def _falhou_conversao(coluna: str, convertida):
    """True quando havia valor na origem e a conversão devolveu NULL."""
    return _preenchido(coluna) & convertida.isNull()


def _grau_decimal(prefixo: str, hemisferios: list[str], negativo: str):
    """Converte graus/minutos/segundos + hemisfério em grau decimal.

    O BDSolos guarda coordenada em DMS separado em quatro colunas. Minutos e
    segundos ausentes contam como zero.

    🚨 **Duas condições invalidam a coordenada inteira, e ambas devolvem NULL:**

    1. **Graus ausente** — não há o que compor.
    2. **Hemisfério ausente ou fora do domínio** — sem ele o *sinal* é
       desconhecido. Assumir positivo por omissão produziria, para o Brasil,
       uma coordenada no hemisfério errado com aparência perfeitamente válida.
       Verificado na fonte: **2.116 linhas têm grau de longitude sem
       hemisfério**, e 88 de latitude. Errar em silêncio nessas seria pior que
       não ter coordenada.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import DoubleType

    graus = _numero(f"{prefixo}_graus", DoubleType())
    minutos = F.coalesce(_numero(f"{prefixo}_minutos", DoubleType()), F.lit(0.0))
    segundos = F.coalesce(_numero(f"{prefixo}_segundos", DoubleType()), F.lit(0.0))
    hemisferio = F.trim(F.col(f"{prefixo}_hemisferio"))

    magnitude = F.abs(graus) + minutos / 60.0 + segundos / 3600.0
    sinal = F.when(hemisferio == negativo, F.lit(-1.0)).otherwise(F.lit(1.0))

    return F.when(
        graus.isNotNull() & hemisferio.isin(hemisferios),
        magnitude * sinal,
    )


@dag(
    dag_id="prata_transforma_bdsolos",
    description="Bronze → Prata: tipagem, separação de grão e rejeição explícita",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    tags=["classolosbr-ns", "prata", "bdsolos"],
    default_args={"retries": 1},
)
def prata_transforma_bdsolos():
    @task
    def transformar() -> dict[str, Any]:
        """Lê a Bronze, tipa, separa os dois grãos e grava Prata em Delta."""
        from delta.tables import DeltaTable
        from pyspark.sql import Window, functions as F
        from pyspark.sql.types import DoubleType, IntegerType

        spark = _sessao_spark("prata-transforma-bdsolos")
        try:
            todas = spark.read.parquet(ORIGEM_BRONZE)

            # Se houver mais de uma ingestão acumulada, processa só a mais
            # recente — senão as contagens somariam versões do mesmo arquivo.
            ultima = todas.agg(F.max("_ingestao_ts")).collect()[0][0]
            if ultima is None:
                raise AirflowFailException(
                    f"Bronze vazia em {ORIGEM_BRONZE}. Rode bronze_ingest_bdsolos antes."
                )
            bronze = todas.filter(F.col("_ingestao_ts") == F.lit(ultima)).cache()

            # Conta a ingestão processada, não o acumulado do bucket: é este o
            # número que a validação compara com a fonte.
            linhas_bronze = bronze.count()

            perfil_id = F.concat_ws("|", *[F.trim(F.col(c)) for c in CHAVE_PERFIL])

            # ---------------- conversões e suas falhas ----------------
            altitude = _numero("altitude_m", DoubleType())
            prof_sup = _numero("profundidade_superior", IntegerType())
            prof_inf = _numero("profundidade_inferior", IntegerType())

            latitude = _grau_decimal("latitude", HEMISFERIOS_LAT, "Sul")
            longitude = _grau_decimal("longitude", HEMISFERIOS_LON, "Oeste")

            hemis_lat = F.trim(F.col("latitude_hemisferio"))
            hemis_lon = F.trim(F.col("longitude_hemisferio"))

            base = bronze.select(
                perfil_id.alias("perfil_id"),
                *[_texto(c).alias(c) for c in CHAVE_PERFIL],
                _texto("uf").alias("uf"),
                _texto("municipio").alias("municipio"),
                altitude.alias("altitude_m"),
                latitude.alias("latitude"),
                longitude.alias("longitude"),
                _texto("datum").alias("datum"),
                _texto("classificacao_original").alias("classificacao_original"),
                _texto("classificacao_atual").alias("classificacao_atual"),
                _texto("classe_de_solos_nivel_1").alias("ordem_sibcs"),
                _texto("simbolo_horizonte").alias("simbolo_horizonte"),
                _texto("codigo_horizonte").alias("codigo_horizonte"),
                prof_sup.alias("profundidade_superior_cm"),
                prof_inf.alias("profundidade_inferior_cm"),
                _numero("carbono_organico", DoubleType()).alias("carbono_organico"),
                _numero("equivalente_de_carbonato_de_calcio", DoubleType())
                .alias("equivalente_caco3"),
                F.col("_ingestao_sha256"),
                F.col("_ingestao_ts"),
                # --- marcadores de problema, avaliados na origem ---
                _falhou_conversao("altitude_m", altitude).alias("_f_altitude"),
                _falhou_conversao("profundidade_superior", prof_sup).alias("_f_prof_sup"),
                _falhou_conversao("profundidade_inferior", prof_inf).alias("_f_prof_inf"),
                (
                    _preenchido("latitude_hemisferio")
                    & ~hemis_lat.isin(HEMISFERIOS_LAT)
                ).alias("_f_hemis_lat"),
                (
                    _preenchido("longitude_hemisferio")
                    & ~hemis_lon.isin(HEMISFERIOS_LON)
                ).alias("_f_hemis_lon"),
                # Hemisfério informado mas graus ausente: coordenada inutilizável.
                # ⚠️ Os parênteses são obrigatórios: em Python `&` liga mais forte
                # que `==`, e sem eles a expressão vira outra coisa em silêncio.
                (
                    _preenchido("latitude_hemisferio")
                    & (~_preenchido("latitude_graus"))
                ).alias("_f_lat_sem_graus"),
                # Registro partido na origem (ver docstring). Duas assinaturas,
                # conferidas contra o arquivo: a metade truncada não tem o link
                # do PDF, que todo registro íntegro tem; a metade deslocada tem
                # código de trabalho que não é número.
                (
                    ~_preenchido("link_para_descricao_em_pdf")
                    | ~F.coalesce(
                        F.trim(F.col("codigo_trabalho")).rlike(r"^[0-9]+$"),
                        F.lit(False),
                    )
                ).alias("_f_registro_partido"),
            ).withColumn("processado_em", F.current_timestamp())

            # ---------------- rejeições (campo a campo, com motivo) ----------------
            motivos = [
                ("_f_altitude", "altitude_m não numérica"),
                ("_f_prof_sup", "profundidade_superior não numérica"),
                ("_f_prof_inf", "profundidade_inferior não numérica"),
                ("_f_hemis_lat", "latitude_hemisferio fora do domínio {Norte,Sul}"),
                ("_f_hemis_lon", "longitude_hemisferio fora do domínio {Leste,Oeste}"),
                ("_f_lat_sem_graus", "hemisfério informado sem graus de latitude"),
                ("_f_registro_partido",
                 "registro partido na origem (aspas internas sem escape)"),
            ]
            expr_motivos = F.array_compact(
                F.array(*[
                    F.when(F.col(flag), F.lit(texto)) for flag, texto in motivos
                ])
            )

            marcada = base.withColumn("_motivos", expr_motivos)

            rejeitados = (
                marcada.filter(F.size("_motivos") > 0)
                .select(
                    "perfil_id", "simbolo_horizonte", "uf", "municipio",
                    F.col("_motivos").alias("motivos"),
                    F.col("_ingestao_sha256"), "processado_em",
                )
            )
            n_rejeitados = rejeitados.count()
            if n_rejeitados:
                rejeitados.write.mode("append").parquet(DESTINO_REJEITADOS)

            # Registro partido não é lido: sai dos dois grãos (ver docstring).
            partidos = marcada.filter("_f_registro_partido")
            n_partidos = partidos.count()
            marcada = marcada.filter(~F.col("_f_registro_partido"))
            # Perfil real cujos registros estão todos partidos: não sobra
            # nada dele para a Prata, e ele é contado aqui para não sumir.
            n_perfis_corrompidos = (
                partidos.filter(
                    F.trim(F.col("codigo_trabalho")).rlike(r"^[0-9]+$")
                )
                .select("perfil_id").distinct()
                .join(marcada.select("perfil_id").distinct(),
                      on="perfil_id", how="left_anti")
                .count()
            )

            # ---------------- grão 1: horizontes ----------------
            # Um horizonte existe quando há símbolo. Linhas sem símbolo são o
            # registro de perfil sem descrição morfológica.
            horizontes = (
                marcada.filter(F.col("simbolo_horizonte").isNotNull())
                .select(
                    "perfil_id", "simbolo_horizonte", "codigo_horizonte",
                    "profundidade_superior_cm", "profundidade_inferior_cm",
                    "carbono_organico",
                    # Necessário para a checagem de coerência do sufixo `k̄`
                    # (ver task `sinalizar_simbolos`): é o único campo que
                    # denuncia um `k̄` perdido na transcrição.
                    "equivalente_caco3",
                    "processado_em",
                )
                # Profundidade invertida é erro de digitação conhecido: sinaliza,
                # não corrige — corrigir seria inventar dado.
                .withColumn(
                    "profundidade_invertida",
                    F.col("profundidade_superior_cm").isNotNull()
                    & F.col("profundidade_inferior_cm").isNotNull()
                    & (F.col("profundidade_superior_cm") > F.col("profundidade_inferior_cm")),
                )
            ).cache()
            n_horizontes = horizontes.count()
            n_prof_invertida = horizontes.filter("profundidade_invertida").count()

            # ---------------- grão 2: perfis ----------------
            colunas_perfil = [
                "perfil_id", *CHAVE_PERFIL, "uf", "municipio", "altitude_m",
                "latitude", "longitude", "datum", "classificacao_original",
                "classificacao_atual", "ordem_sibcs", "_ingestao_sha256",
            ]
            # As colunas de perfil deveriam ser idênticas em todas as linhas do
            # mesmo perfil. 🚨 **Não são** — verificado na fonte: pelo menos um
            # perfil tem `classificacao_original`/`atual` divergindo entre as
            # próprias linhas (4.000 perfis divergem em alguma linha, 3.999 na
            # primeira). Por isso NÃO se usa `dropDuplicates`, que escolheria uma
            # linha de forma **não determinística** e faria a saída variar entre
            # execuções sobre o mesmo dado.
            candidatos = marcada.select(*colunas_perfil).distinct().cache()

            # Perfis cujas colunas de perfil não são constantes entre as linhas.
            divergentes = (
                candidatos.groupBy("perfil_id")
                .agg(F.count("*").alias("_variantes"))
                .filter(F.col("_variantes") > 1)
                .select("perfil_id")
            )
            n_divergentes = divergentes.count()

            # Desempate determinístico: ordena pelo hash da linha inteira, que é
            # estável entre execuções e independe do particionamento.
            ordem_estavel = Window.partitionBy("perfil_id").orderBy(
                F.md5(F.to_json(F.struct(*colunas_perfil)))
            )
            perfis = (
                candidatos.withColumn("_rn", F.row_number().over(ordem_estavel))
                .filter(F.col("_rn") == 1)
                .drop("_rn")
                .join(
                    divergentes.withColumn("atributos_divergentes", F.lit(True)),
                    on="perfil_id",
                    how="left",
                )
                .withColumn(
                    "atributos_divergentes",
                    F.coalesce("atributos_divergentes", F.lit(False)),
                )
                .join(
                    horizontes.groupBy("perfil_id").agg(
                        F.count("*").alias("qtd_horizontes")
                    ),
                    on="perfil_id",
                    how="left",
                )
                .withColumn("qtd_horizontes", F.coalesce("qtd_horizontes", F.lit(0)))
                # ---- flags de qualidade: sinalizam, NÃO filtram ----
                .withColumn("tem_horizonte", F.col("qtd_horizontes") > 0)
                .withColumn(
                    "tem_coordenada",
                    F.col("latitude").isNotNull() & F.col("longitude").isNotNull(),
                )
                # Fisicamente impossível ≠ fora do Brasil: são severidades
                # distintas. A fonte tem graus de longitude até 720 e de
                # latitude até 100 — valores que nenhuma projeção admite.
                .withColumn(
                    "coordenada_impossivel",
                    (F.abs("latitude") > 90) | (F.abs("longitude") > 180),
                )
                .withColumn(
                    "coordenada_no_brasil",
                    F.col("latitude").between(*BRASIL_LAT)
                    & F.col("longitude").between(*BRASIL_LON),
                )
                .withColumn("ordem_valida", F.col("ordem_sibcs").isin(ORDENS_SIBCS))
                .withColumn(
                    "foi_reclassificado",
                    F.col("classificacao_original").isNotNull()
                    & F.col("classificacao_atual").isNotNull()
                    & (_classificacao_comparavel("classificacao_original")
                       != _classificacao_comparavel("classificacao_atual")),
                )
                .withColumn("processado_em", F.current_timestamp())
            ).cache()

            # ---------------- escrita em Delta ----------------
            # `perfis` tem chave natural estável (perfil_id) → MERGE, que preserva
            # linhas de execuções anteriores e atualiza as que mudaram.
            if DeltaTable.isDeltaTable(spark, DESTINO_PERFIS):
                (
                    DeltaTable.forPath(spark, DESTINO_PERFIS)
                    .alias("t")
                    .merge(perfis.alias("s"), "t.perfil_id = s.perfil_id")
                    .whenMatchedUpdateAll()
                    .whenNotMatchedInsertAll()
                    .execute()
                )
            else:
                perfis.write.format("delta").save(DESTINO_PERFIS)

            # ⚠️ `horizontes` NÃO tem chave natural estável: `perfil_id` se repete
            # por definição (é 1:N), e não há identificador único de horizonte
            # verificado na fonte. Fazer MERGE por perfil_id casaria o horizonte
            # errado. Reescreve-se a tabela inteira — barato nesta escala, e o
            # histórico fica preservado pelo próprio log do Delta.
            horizontes.write.format("delta").mode("overwrite").save(DESTINO_HORIZONTES)

            resumo = {
                "linhas_bronze": linhas_bronze,
                "registros_partidos": n_partidos,
                "perfis": perfis.count(),
                "perfis_descartados_corrompidos": n_perfis_corrompidos,
                "horizontes": n_horizontes,
                "perfis_sem_horizonte": perfis.filter(~F.col("tem_horizonte")).count(),
                "perfis_com_horizonte": perfis.filter("tem_horizonte").count(),
                "perfis_sem_coordenada": perfis.filter(~F.col("tem_coordenada")).count(),
                "perfis_coord_fora_do_brasil": perfis.filter(
                    F.col("tem_coordenada") & ~F.col("coordenada_no_brasil")
                ).count(),
                "perfis_coord_impossivel": perfis.filter("coordenada_impossivel").count(),
                "perfis_atributos_divergentes": n_divergentes,
                "perfis_ordem_invalida": perfis.filter(~F.col("ordem_valida")).count(),
                "perfis_reclassificados": perfis.filter("foi_reclassificado").count(),
                "horizontes_prof_invertida": n_prof_invertida,
                "linhas_com_rejeicao": n_rejeitados,
            }
            print(json.dumps(resumo, indent=2, ensure_ascii=False))
            return resumo
        finally:
            spark.stop()

    @task
    def validar(resumo: dict[str, Any]) -> dict[str, Any]:
        """Compara com os números medidos na fonte. Falha dura em divergência."""
        problemas = [
            f"{chave}: esperado {esperado}, obtido {resumo[chave]}"
            for chave, esperado in ESPERADO.items()
            if resumo.get(chave) != esperado
        ]
        if problemas:
            raise AirflowFailException(
                "Prata divergiu dos valores medidos em 2026-08-31:\n  - "
                + "\n  - ".join(problemas)
                + "\nInvestigue antes de ajustar: divergência aqui costuma ser "
                "mudança de critério ou de fonte, não ruído."
            )
        print("Validação Prata OK.")
        return resumo

    @task
    def sinalizar_simbolos(resumo: dict[str, Any]) -> dict[str, Any]:
        """Aplica a gramática de símbolos aos horizontes. Sinaliza, NÃO filtra.

        `SIMB_HORIZ` não é rótulo descritivo: é a entrada que decide a classe no
        motor de referência. Símbolo malformado não gera erro — gera
        classificação errada em silêncio. Esta task confere cada símbolo contra
        a norma e grava os achados em tabela **separada**, sem tocar em
        `horizontes`: quem consome decide o que fazer.

        ⚠️ Sem UDF, de propósito. São ~1.473 símbolos distintos para ~33.327
        horizontes: validar os distintos no driver e juntar de volta faz 22×
        menos avaliações e, sobretudo, **não exige enviar o módulo ao executor**
        — o que quebraria no profile de cluster sem um `addPyFile`.
        """
        from pyspark.sql import Window, functions as F
        from pyspark.sql.types import (
            ArrayType, BooleanType, StringType, StructField, StructType,
        )

        from sentinela.gramatica_sufixos import (
            LIMIAR_CACO3, DELTA_CACO3, leituras, valida,
        )

        spark = _sessao_spark("prata-sinaliza-simbolos")
        try:
            horizontes = spark.read.format("delta").load(DESTINO_HORIZONTES)

            distintos = [
                linha["simbolo_horizonte"]
                for linha in horizontes.select("simbolo_horizonte").distinct().collect()
                if linha["simbolo_horizonte"] is not None
            ]

            esquema = StructType([
                StructField("simbolo_horizonte", StringType(), False),
                StructField("achados", ArrayType(StructType([
                    StructField("codigo", StringType(), False),
                    StructField("gravidade", StringType(), False),
                    StructField("mensagem", StringType(), False),
                ])), False),
                StructField("gravidade_max", StringType(), True),
                StructField("tem_k_simples", BooleanType(), False),
                StructField("leitura_atual", StringType(), True),
            ])

            # Ordem de severidade; None quando o símbolo não gera achado algum.
            ordem = ["erro", "alerta", "suspeita", "nota"]
            analisados = []
            for simbolo in distintos:
                achados = valida(simbolo, EDICAO_NORMA)
                graves = [g for g in ordem if any(a.gravidade == g for a in achados)]
                candidatas = leituras(simbolo)
                analisados.append((
                    simbolo,
                    [(a.codigo, a.gravidade, a.mensagem) for a in achados],
                    graves[0] if graves else None,
                    # `k` simples (sem a barra) num símbolo — condição necessária
                    # para suspeitar de `k̄` perdido na transcrição.
                    any(s == "k" for s in _sufixos_de(simbolo)),
                    candidatas[0] if len(candidatas) == 1 else None,
                ))
            analise = spark.createDataFrame(analisados, schema=esquema)

            # CaCO₃ do horizonte imediatamente subjacente, para o segundo
            # critério de `k̄` (≥ 50 g·kg⁻¹ a mais que o de baixo).
            abaixo = Window.partitionBy("perfil_id").orderBy(
                F.col("profundidade_superior_cm").asc_nulls_last()
            )
            achados = (
                horizontes
                .withColumn("_caco3_subjacente", F.lead("equivalente_caco3").over(abaixo))
                .join(analise, on="simbolo_horizonte", how="left")
                .withColumn(
                    "k_barra_candidato",
                    F.col("tem_k_simples")
                    & (F.col("equivalente_caco3") >= F.lit(LIMIAR_CACO3))
                    & (
                        F.col("_caco3_subjacente").isNull()
                        | (
                            F.col("equivalente_caco3") - F.col("_caco3_subjacente")
                            >= F.lit(DELTA_CACO3)
                        )
                    ),
                )
                .withColumn("k_barra_candidato", F.coalesce("k_barra_candidato", F.lit(False)))
                .withColumn("edicao_norma", F.lit(EDICAO_NORMA))
                .withColumn("processado_em", F.current_timestamp())
                .select(
                    "perfil_id", "simbolo_horizonte", "codigo_horizonte",
                    "profundidade_superior_cm", "profundidade_inferior_cm",
                    "equivalente_caco3", "achados", "gravidade_max",
                    "leitura_atual", "k_barra_candidato", "edicao_norma",
                    "processado_em",
                )
            ).cache()

            # Reescreve inteiro, como `horizontes` — pelo mesmo motivo: não há
            # chave natural estável de horizonte na fonte.
            achados.write.format("delta").mode("overwrite").save(DESTINO_ACHADOS)

            por_gravidade = {
                g: achados.filter(F.col("gravidade_max") == g).count()
                for g in ordem
            }
            resumo = dict(resumo)
            resumo.update({
                "simbolos_distintos": len(distintos),
                "horizontes_conformes": achados.filter(
                    F.col("gravidade_max").isNull()
                ).count(),
                "horizontes_com_erro": por_gravidade["erro"],
                "horizontes_com_alerta": por_gravidade["alerta"],
                "horizontes_notacao_legada": achados.filter(
                    F.exists("achados", lambda a: a["codigo"] == "NOTACAO_LEGADA")
                ).count(),
                "horizontes_k_barra_candidato": achados.filter("k_barra_candidato").count(),
                "edicao_norma": EDICAO_NORMA,
            })
            print(json.dumps(
                {k: resumo[k] for k in resumo if k.startswith(("simbolos", "horizontes_", "edicao"))},
                indent=2, ensure_ascii=False,
            ))
            return resumo
        finally:
            spark.stop()

    @task
    def relatorio_qualidade(resumo: dict[str, Any]) -> str:
        """Grava o perfil de qualidade da rodada — o dado para o Cap. 5."""
        import boto3

        total = resumo["perfis"] or 1  # guarda contra divisão por zero
        relatorio = {
            "gerado_em": pendulum.now("UTC").to_iso8601_string(),
            "contagens": resumo,
            "percentuais": {
                "perfis_sem_horizonte": round(
                    100 * resumo["perfis_sem_horizonte"] / total, 2
                ),
                "perfis_sem_coordenada": round(
                    100 * resumo["perfis_sem_coordenada"] / total, 2
                ),
                "perfis_reclassificados": round(
                    100 * resumo["perfis_reclassificados"] / total, 2
                ),
            },
            "nota": (
                "Flags sinalizam, não filtram: perfis sem horizonte e sem "
                "coordenada permanecem na tabela Prata."
            ),
        }
        s3 = boto3.client(
            "s3",
            endpoint_url=os.environ["S3_ENDPOINT"],
            aws_access_key_id=os.environ["S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        )
        chave = f"_qualidade/prata-{pendulum.now('UTC').format('YYYYMMDD-HHmmss')}.json"
        s3.put_object(
            Bucket=BUCKET_SILVER,
            Key=chave,
            Body=json.dumps(relatorio, indent=2, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"Relatório em s3://{BUCKET_SILVER}/{chave}")
        return chave

    relatorio_qualidade(sinalizar_simbolos(validar(transformar())))


prata_transforma_bdsolos()
