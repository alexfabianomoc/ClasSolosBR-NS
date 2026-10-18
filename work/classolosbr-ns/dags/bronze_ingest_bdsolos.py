"""Bronze — ingestão do BDSolos (CSV bruto) para Parquet em S3/MinIO.

Camada Bronze do medallion: preserva a fonte como ela é. Nenhum campo é
convertido, limpo ou descartado — todas as 275 colunas entram como texto.
A tipagem acontece na Prata, onde há para onde mandar o que falhar.

Fonte: raw/bd_solos_para_redape.csv (Embrapa/Redape, DOI 10.48432/DDBVFO),
montado somente-leitura pelo docker-compose. Verificado em 2026-08-31:
275 colunas · 34.108 registros · 8.925 chaves de perfil distintas.

⚠️ Revisto em 2026-10-14: os números acima são do arquivo **como o leitor o
parte**, e não do acervo. Três horizontes do perfil 797|12743|RS-142 têm aspas
internas sem escape e saem partidos em dois registros cada — seis registros
para três horizontes —, e as metades deslocadas formam uma chave fantasma
(`;";Campo natural."`). O acervo real tem 34.105 horizontes e 8.924 perfis.
A Bronze preserva os seis registros como vieram, por definição; quem os
rejeita, com motivo, é a Prata.

Idempotência: o SHA-256 do arquivo é gravado num manifesto no bucket Bronze.
Reexecutar com o mesmo arquivo encerra o DAG antes de escrever qualquer coisa.

⚠️ Imports pesados (pyspark, boto3) ficam DENTRO das tasks de propósito. O
scheduler reinterpreta este arquivo a cada 30 s; importar PySpark no topo
tornaria o parsing do DAG lento o bastante para atrasar todo o scheduler.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from typing import Any

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException

# --- Configuração (toda por variável de ambiente; ver .env.example) ---
CSV_FONTE = os.environ.get("BDSOLOS_CSV", "/opt/airflow/raw/bd_solos_para_redape.csv")
BUCKET_BRONZE = os.environ.get("S3_BUCKET_BRONZE", "bronze")
PREFIXO_TABELA = "bdsolos"
PREFIXO_MANIFESTO = f"{PREFIXO_TABELA}/_manifesto"

# Formato do CSV, conferido contra o arquivo real (não presumido).
CSV_SEPARADOR = ";"
CSV_ENCODING = "UTF-8"

# Chave de perfil do BDSolos. Nenhuma coluna isolada identifica um perfil:
# só a tripla separa os perfis (`Código PA` sozinho dá 8.175 chaves; a tripla,
# 8.925, das quais uma é a chave fantasma do registro partido — ver docstring).
CHAVE_PERFIL = ["codigo_trabalho", "codigo_pa", "numero_pa"]

# Contagens esperadas. Divergência aqui significa que a fonte mudou —
# é para o DAG falhar e alguém investigar, não para ajustar o número.
HORIZONTES_ESPERADOS = int(os.environ.get("BDSOLOS_HORIZONTES_ESPERADOS", "34108"))
PERFIS_ESPERADOS = int(os.environ.get("BDSOLOS_PERFIS_ESPERADOS", "8925"))
COLUNAS_ESPERADAS = int(os.environ.get("BDSOLOS_COLUNAS_ESPERADAS", "275"))


def _sanear(nome: str) -> str:
    """Converte um cabeçalho do CSV em nome físico válido para Parquet.

    O Spark recusa escrever Parquet com ` ,;{}()\\n\\t=` no nome da coluna, e o
    BDSolos tem vários casos ("Altitude (m)", "Responsável(is) pela Descrição").
    O nome original não se perde: vai para o mapa de colunas gravado junto ao
    Bronze, então a rastreabilidade até a fonte continua intacta.
    """
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^0-9a-zA-Z]+", "_", sem_acento).strip("_").lower()
    return limpo or "coluna_sem_nome"


def _sanear_todos(nomes: list[str]) -> list[str]:
    """Aplica _sanear preservando unicidade (sufixa colisões com _2, _3...)."""
    vistos: dict[str, int] = {}
    saida: list[str] = []
    for nome in nomes:
        base = _sanear(nome)
        vistos[base] = vistos.get(base, 0) + 1
        saida.append(base if vistos[base] == 1 else f"{base}_{vistos[base]}")
    return saida


def _cliente_s3():
    """Cliente boto3 apontado para o MinIO (ou S3 real, trocando o endpoint)."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    )


def _sessao_spark(nome_app: str):
    """SparkSession em local mode, com Delta e acesso ao MinIO via s3a.

    Local mode é decisão de projeto, não limitação: 34.108 linhas cabem
    folgadamente na memória do driver, e um cluster só acrescentaria
    coordenação de rede a um trabalho que dura segundos. O profile "spark"
    do docker-compose sobe um cluster quando SPARK_MASTER_URL é preenchido.
    """
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    master = os.environ.get("SPARK_MASTER_URL") or "local[*]"

    construtor = (
        SparkSession.builder.appName(nome_app)
        .master(master)
        .config("spark.driver.memory", "2g")
        .config("spark.sql.session.timeZone", "UTC")
        # --- Delta Lake ---
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        # --- Acesso ao MinIO ---
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
    # Os JARs já vêm no ~/.ivy2 da imagem (pré-baixados no Dockerfile).
    return configure_spark_with_delta_pip(
        construtor,
        extra_packages=["org.apache.hadoop:hadoop-aws:3.3.4"],
    ).getOrCreate()


@dag(
    dag_id="bronze_ingest_bdsolos",
    description="Ingere o CSV do BDSolos na camada Bronze (Parquet em S3/MinIO)",
    schedule=None,  # disparo manual: a fonte é um dataset publicado, não um fluxo
    start_date=pendulum.datetime(2026, 8, 1, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    tags=["classolosbr-ns", "bronze", "bdsolos"],
    default_args={"retries": 1},
)
def bronze_ingest_bdsolos():
    @task
    def inspecionar_fonte() -> dict[str, Any]:
        """Confere que o CSV existe e calcula seu SHA-256 (chave de idempotência)."""
        if not os.path.isfile(CSV_FONTE):
            raise AirflowFailException(
                f"CSV do BDSolos não encontrado em {CSV_FONTE}. "
                "Confira o volume ../../raw no docker-compose.yml."
            )

        digest = hashlib.sha256()
        with open(CSV_FONTE, "rb") as fp:
            for bloco in iter(lambda: fp.read(1024 * 1024), b""):
                digest.update(bloco)

        meta = {
            "caminho": CSV_FONTE,
            "arquivo": os.path.basename(CSV_FONTE),
            "bytes": os.path.getsize(CSV_FONTE),
            "sha256": digest.hexdigest(),
        }
        print(f"Fonte: {meta['arquivo']} · {meta['bytes'] / 1e6:.1f} MB · {meta['sha256'][:12]}…")
        return meta

    @task.short_circuit
    def ainda_nao_ingerido(meta: dict[str, Any]) -> bool:
        """Interrompe o DAG se este SHA-256 já estiver no manifesto."""
        from botocore.exceptions import ClientError

        s3 = _cliente_s3()
        chave = f"{PREFIXO_MANIFESTO}/{meta['sha256']}.json"
        try:
            s3.head_object(Bucket=BUCKET_BRONZE, Key=chave)
        except ClientError as erro:
            # 404 (chave ausente) e 403 do MinIO = ainda não ingerido.
            # Qualquer outro código é falha real de infraestrutura.
            codigo = erro.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if codigo in (403, 404):
                return True
            raise
        print(f"Arquivo já ingerido (manifesto {chave}). Nada a fazer.")
        return False

    @task
    def ingerir(meta: dict[str, Any]) -> dict[str, Any]:
        """Lê o CSV como texto puro e grava Parquet particionado na Bronze."""
        from pyspark.sql import functions as F

        spark = _sessao_spark("bronze-ingest-bdsolos")
        try:
            # inferSchema desligado: Bronze não interpreta, só preserva.
            # multiLine porque campos livres do BDSolos contêm quebras de linha.
            bruto = (
                spark.read.option("header", True)
                .option("sep", CSV_SEPARADOR)
                .option("encoding", CSV_ENCODING)
                .option("quote", '"')
                .option("escape", '"')
                .option("multiLine", True)
                .option("inferSchema", False)
                .csv(meta["caminho"])
            )

            originais = bruto.columns
            saneadas = _sanear_todos(originais)
            df = bruto.toDF(*saneadas)

            data_ingestao = pendulum.now("UTC").to_date_string()
            df = (
                df.withColumn("_ingestao_arquivo", F.lit(meta["arquivo"]))
                .withColumn("_ingestao_sha256", F.lit(meta["sha256"]))
                .withColumn("_ingestao_ts", F.current_timestamp())
                .withColumn("_ingestao_data", F.lit(data_ingestao))
            )

            destino = f"s3a://{BUCKET_BRONZE}/{PREFIXO_TABELA}/"
            df.write.mode("append").partitionBy("_ingestao_data").parquet(destino)

            resultado = {
                "linhas": df.count(),
                "colunas": len(originais),
                "perfis": df.select(*CHAVE_PERFIL).distinct().count(),
                "destino": destino,
                "particao": data_ingestao,
                "mapa_colunas": dict(zip(originais, saneadas)),
            }
            print(
                f"Gravado em {destino} · {resultado['linhas']} linhas · "
                f"{resultado['perfis']} perfis"
            )
            return resultado
        finally:
            spark.stop()

    @task
    def validar(resultado: dict[str, Any]) -> dict[str, Any]:
        """Confere o que foi escrito contra os números verificados da fonte.

        Falha dura de propósito: em Bronze, divergência de contagem quase
        sempre é erro de parsing (separador, quote, multiLine) e não fonte
        nova. Deixar passar contamina Prata e Ouro em silêncio.
        """
        problemas: list[str] = []

        if resultado["colunas"] != COLUNAS_ESPERADAS:
            problemas.append(
                f"colunas: esperadas {COLUNAS_ESPERADAS}, obtidas {resultado['colunas']}"
            )
        if resultado["linhas"] != HORIZONTES_ESPERADOS:
            problemas.append(
                f"registros: esperados {HORIZONTES_ESPERADOS}, obtidos {resultado['linhas']}"
            )
        if resultado["perfis"] != PERFIS_ESPERADOS:
            problemas.append(
                f"chaves de perfil: esperadas {PERFIS_ESPERADOS}, obtidas {resultado['perfis']}"
            )

        if problemas:
            raise AirflowFailException(
                "Bronze divergiu da fonte verificada em 2026-08-31:\n  - "
                + "\n  - ".join(problemas)
                + "\nSe a Embrapa publicou uma versão nova, atualize os valores "
                "em .env e registre a mudança no wiki antes de seguir."
            )

        print("Validação Bronze OK: 275 colunas · 34.108 registros · 8.925 chaves "
              "(inclui 6 registros partidos e 1 chave fantasma, rejeitados na Prata).")
        return resultado

    @task
    def registrar_manifesto(meta: dict[str, Any], resultado: dict[str, Any]) -> str:
        """Grava o manifesto que torna a próxima execução um no-op."""
        s3 = _cliente_s3()
        chave = f"{PREFIXO_MANIFESTO}/{meta['sha256']}.json"
        corpo = {
            "fonte": meta,
            "resultado": {k: v for k, v in resultado.items() if k != "mapa_colunas"},
            "mapa_colunas": resultado["mapa_colunas"],
            "ingerido_em": pendulum.now("UTC").to_iso8601_string(),
        }
        s3.put_object(
            Bucket=BUCKET_BRONZE,
            Key=chave,
            Body=json.dumps(corpo, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"Manifesto gravado em s3://{BUCKET_BRONZE}/{chave}")
        return chave

    # Fluxo: inspeciona → (curto-circuito se já ingerido) → ingere → valida →
    # registra manifesto. O short-circuit precisa ser upstream explícito de
    # `ingerir`, senão ela dispararia em paralelo assim que `meta` existisse.
    meta = inspecionar_fonte()
    portao = ainda_nao_ingerido(meta)
    resultado = ingerir(meta)
    validado = validar(resultado)
    registrar_manifesto(meta, validado)

    # Única dependência que não decorre da passagem de dados: sem isto,
    # `ingerir` dispararia em paralelo ao portão assim que `meta` existisse.
    portao >> resultado


bronze_ingest_bdsolos()
