# Imagem do Airflow com PySpark + Delta Lake + acesso a S3/MinIO.
#
# Escolha de projeto: o Spark roda em LOCAL MODE dentro deste contêiner,
# não como cluster. O BDSolos tem 34.108 linhas / 97 MB — um cluster seria
# puro overhead. O cluster existe como profile opcional no docker-compose.yml
# para quem quiser demonstrar a arquitetura distribuída.

FROM apache/airflow:2.10.5-python3.11

# --- Camada root: Java (PySpark exige JVM) ---
USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# --- Camada airflow: dependências Python ---
USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Pré-baixa os JARs do Ivy (hadoop-aws + delta) na build, para que a primeira
# execução do DAG não dependa de rede nem gaste ~1 min baixando dependências.
# As versões precisam casar: PySpark 3.5.x embute cliente Hadoop 3.3.4.
ENV SPARK_JARS_PACKAGES="org.apache.hadoop:hadoop-aws:3.3.4,io.delta:delta-spark_2.12:3.2.0"

RUN python - <<'PY'
from pyspark.sql import SparkSession
import os

# Sessão descartável: o único efeito desejado é popular ~/.ivy2 com os JARs.
spark = (
    SparkSession.builder
    .appName("prefetch-jars")
    .master("local[1]")
    .config("spark.jars.packages", os.environ["SPARK_JARS_PACKAGES"])
    .config("spark.driver.memory", "512m")
    .getOrCreate()
)
spark.stop()
PY

WORKDIR /opt/airflow
