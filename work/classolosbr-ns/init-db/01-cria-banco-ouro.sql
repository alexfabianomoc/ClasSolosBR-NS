-- Executado uma única vez, na primeira subida do contêiner postgres.
-- Cria o banco da camada Ouro, separado do banco de metadados do Airflow.
--
-- Não use \gexec nem variáveis do shell aqui: este script roda pelo
-- entrypoint do Postgres, que já está conectado como superusuário.

CREATE DATABASE classolosbr_ns;

\connect classolosbr_ns

CREATE SCHEMA IF NOT EXISTS ouro;

COMMENT ON SCHEMA ouro IS
  'Camada Ouro do medallion: dados agregados e prontos para consumo pela API.';

-- Tabela-fato mínima, para o pipeline ter destino desde a primeira execução.
-- A modelagem definitiva depende do que o motor simbólico devolver.
CREATE TABLE IF NOT EXISTS ouro.perfis_classificados (
    perfil_id            TEXT PRIMARY KEY,
    codigo_trabalho      TEXT NOT NULL,
    codigo_pa            TEXT NOT NULL,
    numero_pa            TEXT NOT NULL,
    uf                   TEXT,
    municipio            TEXT,
    ordem_sibcs_original TEXT,
    ordem_sibcs_atual    TEXT,
    qtd_horizontes       INTEGER NOT NULL DEFAULT 0,
    atualizado_em        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_perfis_ordem_atual
    ON ouro.perfis_classificados (ordem_sibcs_atual);

CREATE INDEX IF NOT EXISTS idx_perfis_uf
    ON ouro.perfis_classificados (uf);
