# Databricks notebook source
# MAGIC %md
# MAGIC # DLA Medical Supply Readiness — Synthetic Data Generator
# MAGIC
# MAGIC This notebook generates **managed Delta tables** directly in the current/default Databricks catalog.
# MAGIC
# MAGIC All operational data is synthetic. Official public DLA scale metrics are stored separately in `reference_enterprise_metrics`.

# COMMAND ----------
from datetime import date
from pathlib import Path
import sys

# In Databricks Git folders / modern runtimes, the notebook working directory is
# this notebook's folder. Add ../src so the generator remains modular.
src_path = str((Path.cwd().parent / "src").resolve())
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from dla_supply_demo import GenerationConfig, SCALE_PROFILES, expected_scale, generate_all
from dla_supply_demo.common import fq_table

# COMMAND ----------
# MAGIC %md
# MAGIC ## Parameters
# MAGIC Leave `catalog_name` blank to use the workspace/session's current catalog.
# MAGIC The recommended first run is `tiny`; once validated, rerun with `demo`.

# COMMAND ----------
dbutils.widgets.dropdown("scale", "tiny", list(SCALE_PROFILES.keys()), "Generation scale")
dbutils.widgets.text("catalog_name", "", "Catalog (blank = current/default)")
dbutils.widgets.text("schema_name", "dla_medical_supply_demo", "Schema")
dbutils.widgets.text("as_of_date", date.today().isoformat(), "As-of date (YYYY-MM-DD)")
dbutils.widgets.dropdown("reset", "true", ["true", "false"], "Drop/recreate generated tables")

scale_name = dbutils.widgets.get("scale").strip()
catalog_override = dbutils.widgets.get("catalog_name").strip()
schema_name = dbutils.widgets.get("schema_name").strip()
as_of_date = date.fromisoformat(dbutils.widgets.get("as_of_date").strip())
reset = dbutils.widgets.get("reset").lower() == "true"

catalog_name = catalog_override or spark.catalog.currentCatalog()

cfg = GenerationConfig(
    catalog_name=catalog_name,
    schema_name=schema_name,
    as_of_date=as_of_date,
    scale_name=scale_name,
)

print(f"Catalog: {cfg.catalog_name}")
print(f"Schema: {cfg.schema_name}")
print(f"As-of date: {cfg.as_of_date}")
print(f"Scale: {cfg.scale_name}")
print(f"History starts: {cfg.start_date}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Expected synthetic scale
# MAGIC These are generated demo counts, **not official DLA counts**.

# COMMAND ----------
scale_rows = [(k, int(v)) for k, v in expected_scale(cfg).items()]
display(spark.createDataFrame(scale_rows, ["metric", "expected_value"]))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Generate managed Delta tables

# COMMAND ----------
generate_all(spark, cfg, reset=reset)
print("Synthetic DLA medical supply data generation complete.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Registered tables

# COMMAND ----------
display(
    spark.sql(
        f"SHOW TABLES IN `{cfg.catalog_name.replace('`', '``')}`.`{cfg.schema_name.replace('`', '``')}`"
    )
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Model target sanity check
# MAGIC A useful training set should contain both shortage and non-shortage outcomes.

# COMMAND ----------
training = spark.table(fq_table(cfg, "ml_shortage_training"))
display(
    training.groupBy("shortage_within_30d")
    .count()
    .orderBy("shortage_within_30d")
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Current operational watch list
# MAGIC This is **not** the DataRobot prediction. It simply shows current inventory positions closest to/below their minimum policy threshold.

# COMMAND ----------
current_position = spark.table(fq_table(cfg, "agent_current_supply_position"))
display(
    current_position
    .orderBy("days_above_minimum", "criticality")
    .select(
        "customer_name",
        "region",
        "item_name",
        "criticality",
        "days_of_supply",
        "minimum_days_supply",
        "days_above_minimum",
        "backordered_orders",
        "late_inbound_units",
        "supplier_name",
        "actual_ontime_rate_90d",
    )
    .limit(25)
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Public DLA scale reference
# MAGIC These rows are kept separate from the synthetic facts and include source URLs/provenance.

# COMMAND ----------
display(spark.table(fq_table(cfg, "reference_enterprise_metrics")))
