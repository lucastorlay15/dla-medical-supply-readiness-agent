# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Validate DLA Medical Supply Demo Data
# MAGIC
# MAGIC Run this after `00_generate_all` to inspect model prevalence, current supply health, supplier behavior, and basic referential integrity.

# COMMAND ----------

from datetime import date
from pathlib import Path
import sys

from pyspark.sql import functions as F
from pyspark.sql.window import Window

src_path = str((Path.cwd().parent / "src").resolve())
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from dla_supply_demo.common import fq_table
from dla_supply_demo.config import GenerationConfig

# COMMAND ----------

dbutils.widgets.text("catalog_name", "", "Catalog (blank = current/default)")
dbutils.widgets.text("schema_name", "dla_medical_supply_demo", "Schema")

catalog_name = dbutils.widgets.get("catalog_name").strip() or spark.catalog.currentCatalog()
schema_name = dbutils.widgets.get("schema_name").strip()

# as_of_date/scale are not needed to read already-generated tables.
cfg = GenerationConfig(
    catalog_name=catalog_name,
    schema_name=schema_name,
    as_of_date=date.today(),
    scale_name="tiny",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table inventory and physical size

# COMMAND ----------

table_names = [
    "dim_customer_location",
    "dim_medical_item",
    "dim_supplier",
    "bridge_customer_item",
    "fact_inventory_daily",
    "fact_orders",
    "fact_shipments",
    "fact_supplier_events",
    "analytics_supplier_performance",
    "agent_current_supply_position",
    "ml_shortage_training",
    "ml_shortage_scoring",
    "reference_enterprise_metrics",
]

sizes = []
for table in table_names:
    detail = spark.sql(f"DESCRIBE DETAIL {fq_table(cfg, table)}").first().asDict()
    sizes.append(
        (
            table,
            int(detail.get("numFiles", 0) or 0),
            int(detail.get("sizeInBytes", 0) or 0),
        )
    )

display(
    spark.createDataFrame(sizes, ["table", "num_files", "size_bytes"])
    .withColumn("size_mb", F.round(F.col("size_bytes") / F.lit(1024.0 * 1024.0), 2))
    .orderBy(F.desc("size_bytes"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Model target prevalence

# COMMAND ----------

training = spark.table(fq_table(cfg, "ml_shortage_training"))
target_summary = (
    training.groupBy("shortage_within_30d")
    .count()
    .withColumn("share", F.col("count") / F.sum("count").over(Window.partitionBy()))
    .orderBy("shortage_within_30d")
)
display(target_summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Current supply health

# COMMAND ----------

current = spark.table(fq_table(cfg, "agent_current_supply_position"))
display(
    current.groupBy("inventory_status")
    .agg(
        F.count("*").alias("customer_item_positions"),
        F.round(F.sum("inventory_value_usd"), 2).alias("inventory_value_usd"),
    )
    .orderBy(F.desc("customer_item_positions"))
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## High-value current concerns for the eventual agent demo

# COMMAND ----------

display(
    current
    .filter(F.col("criticality").isin("MISSION_CRITICAL", "HIGH"))
    .orderBy("days_above_minimum", F.desc("late_inbound_units"))
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
        "contract_lead_time_days",
        "actual_ontime_rate_90d",
        "policy_reference_id",
    )
    .limit(30)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Referential integrity checks

# COMMAND ----------

inventory = spark.table(fq_table(cfg, "fact_inventory_daily"))
customers = spark.table(fq_table(cfg, "dim_customer_location"))
items = spark.table(fq_table(cfg, "dim_medical_item"))
suppliers = spark.table(fq_table(cfg, "dim_supplier"))

checks = [
    (
        "inventory rows with unknown customer",
        inventory.select("customer_id").distinct().join(
            customers.select("customer_id"), "customer_id", "left_anti"
        ).count(),
    ),
    (
        "inventory rows with unknown item",
        inventory.select("item_id").distinct().join(
            items.select("item_id"), "item_id", "left_anti"
        ).count(),
    ),
    (
        "inventory rows with unknown preferred supplier",
        inventory.select("preferred_supplier_id").distinct().join(
            suppliers.select(F.col("supplier_id").alias("preferred_supplier_id")),
            "preferred_supplier_id",
            "left_anti",
        ).count(),
    ),
]

display(spark.createDataFrame(checks, ["check", "failures"]))

assert all(failures == 0 for _, failures in checks), "Referential integrity validation failed."
print("Validation passed.")