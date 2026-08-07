from typing import Iterable

from pyspark.sql import DataFrame, SparkSession

from .config import GenerationConfig


def quote_identifier(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


def fq_table(cfg: GenerationConfig, table: str) -> str:
    return ".".join(
        [
            quote_identifier(cfg.catalog_name),
            quote_identifier(cfg.schema_name),
            quote_identifier(table),
        ]
    )


def ensure_schema(spark: SparkSession, cfg: GenerationConfig) -> None:
    catalog = quote_identifier(cfg.catalog_name)
    schema = quote_identifier(cfg.schema_name)
    spark.sql(
        f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema} "
        "COMMENT 'Synthetic DLA medical supply readiness demo data'"
    )
    spark.sql(f"USE CATALOG {catalog}")
    spark.sql(f"USE SCHEMA {schema}")


def write_delta(
    df: DataFrame,
    spark: SparkSession,
    cfg: GenerationConfig,
    table: str,
    comment: str,
    partition_by: Iterable[str] = (),
) -> None:
    writer = (
        df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
    )
    partition_cols = list(partition_by)
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.saveAsTable(fq_table(cfg, table))
    escaped_comment = comment.replace("'", "''")
    spark.sql(f"COMMENT ON TABLE {fq_table(cfg, table)} IS '{escaped_comment}'")


def drop_tables(spark: SparkSession, cfg: GenerationConfig, tables: Iterable[str]) -> None:
    for table in tables:
        spark.sql(f"DROP TABLE IF EXISTS {fq_table(cfg, table)}")


def table_count(spark: SparkSession, cfg: GenerationConfig, table: str) -> int:
    return spark.table(cfg.table_name(table)).count()
