import math
from typing import Dict

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .common import write_delta
from .config import GenerationConfig


def _pick(values, index_col):
    return F.element_at(
        F.array(*[F.lit(value) for value in values]),
        F.pmod(index_col, F.lit(len(values))).cast("int") + F.lit(1),
    )


def build_dimensions(spark: SparkSession, cfg: GenerationConfig) -> Dict[str, DataFrame]:
    p = cfg.profile

    # ------------------------------------------------------------------
    # Customer locations
    # ------------------------------------------------------------------
    regions = [
        "CONUS East",
        "CONUS West",
        "Europe",
        "Indo-Pacific",
        "Alaska/Hawaii",
        "Central/Southwest Asia",
    ]
    customer_types = [
        "Military Treatment Facility",
        "Operational Medical Unit",
        "Medical Logistics Hub",
        "Public Health Laboratory",
        "Veterinary Activity",
    ]
    services = ["Army", "Navy", "Air Force", "Marine Corps", "Joint", "DHA"]

    customers = (
        spark.range(p.customers)
        .withColumnRenamed("id", "customer_index")
        .withColumn("customer_id", F.format_string("CUST-%05d", F.col("customer_index") + 1))
        .withColumn("region", _pick(regions, F.col("customer_index") * 7 + 3))
        .withColumn("customer_type", _pick(customer_types, F.col("customer_index") * 11 + 1))
        .withColumn("service", _pick(services, F.col("customer_index") * 13 + 2))
        .withColumn(
            "customer_name",
            F.concat(
                F.lit("Synthetic "),
                F.col("region"),
                F.lit(" Medical Site "),
                F.format_string("%03d", F.col("customer_index") + 1),
            ),
        )
        .withColumn(
            "mission_priority",
            (F.pmod(F.xxhash64("customer_index", F.lit(cfg.seed)), F.lit(5)) + 1).cast("int"),
        )
        .withColumn(
            "supported_population",
            (
                F.lit(500)
                + F.pmod(
                    F.xxhash64("customer_id", F.lit(cfg.seed + 1)), F.lit(49_500)
                )
            ).cast("int"),
        )
        .withColumn(
            "remote_location_flag",
            F.col("region").isin("Indo-Pacific", "Alaska/Hawaii", "Central/Southwest Asia"),
        )
    )

    write_delta(
        customers,
        spark,
        cfg,
        "dim_customer_location",
        "Synthetic medical customers/receiving locations supported by the DLA medical supply chain demo.",
    )

    # ------------------------------------------------------------------
    # Medical items. Categories/FSCs mirror publicly described DLA Medical
    # commodity families, but every individual item is synthetic.
    # ------------------------------------------------------------------
    category_rows = [
        (0, "Pharmaceuticals", "6505", 18.0, 30, True),
        (1, "Medical/Surgical", "6515", 7.0, 21, False),
        (2, "Surgical Dressing Materials", "6510", 3.0, 21, False),
        (3, "Dental Items", "6520", 12.0, 14, False),
        (4, "Biomedical Equipment", "6525", 950.0, 30, False),
        (5, "Optical Items", "6540", 35.0, 14, False),
        (6, "Replenishable Field Kits", "6545", 220.0, 30, False),
        (7, "Diagnostic Kits/Reagents", "6550", 42.0, 21, True),
        (8, "Laboratory Items", "6640", 75.0, 21, False),
        (9, "Critical Care", "6515", 125.0, 30, False),
        (10, "Preventive Vaccines", "6505", 55.0, 30, True),
        (11, "Veterinary Pharmaceuticals", "6509", 22.0, 21, True),
    ]
    category_schema = [
        "category_index",
        "commodity_group",
        "fsc_code",
        "base_unit_cost",
        "base_min_days_supply",
        "category_cold_chain",
    ]
    categories = spark.createDataFrame(category_rows, category_schema)

    items = (
        spark.range(p.items)
        .withColumnRenamed("id", "item_index")
        .withColumn("category_index", F.pmod(F.col("item_index") * 7 + 3, F.lit(len(category_rows))).cast("int"))
        .join(categories, "category_index")
        .withColumn("item_id", F.format_string("MED-%06d", F.col("item_index") + 1))
        .withColumn(
            "item_name",
            F.concat(
                F.col("commodity_group"),
                F.lit(" Synthetic Item "),
                F.format_string("%04d", F.col("item_index") + 1),
            ),
        )
        .withColumn(
            "criticality",
            F.when(F.pmod(F.xxhash64("item_id"), F.lit(100)) < 18, F.lit("MISSION_CRITICAL"))
            .when(F.pmod(F.xxhash64("item_id"), F.lit(100)) < 55, F.lit("HIGH"))
            .otherwise(F.lit("ROUTINE")),
        )
        .withColumn(
            "policy_min_days_supply",
            (
                F.col("base_min_days_supply")
                + F.when(F.col("criticality") == "MISSION_CRITICAL", 7)
                .when(F.col("criticality") == "HIGH", 3)
                .otherwise(0)
            ).cast("int"),
        )
        .withColumn(
            "unit_cost_usd",
            F.round(
                F.col("base_unit_cost")
                * (
                    F.lit(0.65)
                    + F.pmod(F.xxhash64("item_id", F.lit(cfg.seed)), F.lit(1000)) / F.lit(800.0)
                ),
                2,
            ),
        )
        .withColumn(
            "cold_chain_required",
            F.col("category_cold_chain")
            & (F.pmod(F.xxhash64("item_id", F.lit(91)), F.lit(100)) < 70),
        )
        .withColumn(
            "shelf_life_days",
            F.when(F.col("commodity_group").isin("Preventive Vaccines", "Diagnostic Kits/Reagents"), 365)
            .when(F.col("commodity_group").isin("Pharmaceuticals", "Veterinary Pharmaceuticals"), 730)
            .otherwise(1460),
        )
        .withColumn("policy_reference_id", F.concat(F.lit("MED-STOCK-"), F.col("fsc_code")))
        .drop("base_unit_cost", "base_min_days_supply", "category_cold_chain")
    )

    write_delta(
        items,
        spark,
        cfg,
        "dim_medical_item",
        "Synthetic medical item master with commodity group, criticality, cost, storage, and policy reference metadata.",
    )

    # ------------------------------------------------------------------
    # Suppliers
    # ------------------------------------------------------------------
    supplier_regions = ["CONUS", "Europe", "Indo-Pacific", "Canada", "Allied Partner"]
    supplier_types = ["Manufacturer", "Prime Vendor", "Wholesaler", "Distributor"]

    suppliers = (
        spark.range(p.suppliers)
        .withColumnRenamed("id", "supplier_index")
        .withColumn("supplier_id", F.format_string("SUP-%05d", F.col("supplier_index") + 1))
        .withColumn("supplier_name", F.concat(F.lit("Synthetic Medical Supplier "), F.format_string("%03d", F.col("supplier_index") + 1)))
        .withColumn("supplier_region", _pick(supplier_regions, F.col("supplier_index") * 5 + 2))
        .withColumn("supplier_type", _pick(supplier_types, F.col("supplier_index") * 3 + 1))
        .withColumn(
            "contract_lead_time_days",
            (
                F.lit(7)
                + F.pmod(F.xxhash64("supplier_id", F.lit(cfg.seed + 10)), F.lit(63))
            ).cast("int"),
        )
        .withColumn(
            "baseline_ontime_rate",
            F.round(
                F.lit(0.76)
                + F.pmod(F.xxhash64("supplier_id", F.lit(cfg.seed + 11)), F.lit(2300)) / F.lit(10_000.0),
                4,
            ),
        )
        .withColumn(
            "quality_acceptance_rate",
            F.round(
                F.lit(0.965)
                + F.pmod(F.xxhash64("supplier_id", F.lit(cfg.seed + 12)), F.lit(340)) / F.lit(10_000.0),
                4,
            ),
        )
        .withColumn(
            "small_business_flag",
            F.pmod(F.xxhash64("supplier_id", F.lit(123)), F.lit(100)) < 55,
        )
    )

    write_delta(
        suppliers,
        spark,
        cfg,
        "dim_supplier",
        "Synthetic supplier master with lead-time, service-level, geography, and quality characteristics.",
    )

    # ------------------------------------------------------------------
    # Active customer-item relationships. This keeps the daily fact table
    # realistic and sparse instead of cross-joining every item to every site.
    # ------------------------------------------------------------------
    slots = spark.range(p.active_items_per_customer).withColumnRenamed("id", "item_slot")
    relationships = (
        customers.select(
            "customer_id",
            "customer_index",
            "mission_priority",
            "supported_population",
            "region",
        )
        .crossJoin(slots)
        .withColumn(
            "item_index",
            F.pmod(
                F.col("customer_index") * F.lit(37) + F.col("item_slot") * F.lit(53),
                F.lit(p.items),
            ).cast("long"),
        )
        .join(
            items.select(
                "item_id",
                "item_index",
                "criticality",
                "commodity_group",
                "unit_cost_usd",
                "policy_min_days_supply",
                "cold_chain_required",
            ),
            "item_index",
        )
        .withColumn(
            "preferred_supplier_index",
            F.pmod(
                F.col("item_index") * F.lit(17) + F.col("customer_index") * F.lit(13),
                F.lit(p.suppliers),
            ).cast("long"),
        )
        .join(
            suppliers.select(
                F.col("supplier_index").alias("preferred_supplier_index"),
                F.col("supplier_id").alias("preferred_supplier_id"),
                "contract_lead_time_days",
                "baseline_ontime_rate",
                "quality_acceptance_rate",
            ),
            "preferred_supplier_index",
        )
        .withColumn(
            "minimum_days_supply",
            (
                F.col("policy_min_days_supply")
                + F.when(F.col("mission_priority") >= 4, 3).otherwise(0)
            ).cast("int"),
        )
        .withColumn(
            "target_days_supply",
            (
                F.col("minimum_days_supply")
                + F.lit(9)
                + F.pmod(F.xxhash64("customer_id", "item_id"), F.lit(11))
            ).cast("int"),
        )
        .withColumn(
            "baseline_daily_demand",
            F.round(
                F.lit(0.8)
                + (F.col("supported_population") / F.lit(8_000.0))
                + F.pmod(
                    F.xxhash64("customer_id", "item_id", F.lit(cfg.seed + 20)), F.lit(2_500)
                )
                / F.lit(100.0),
                2,
            ),
        )
        # Internal latent stress drives synthetic shortages. It is deliberately
        # excluded from the published bridge/model features to avoid leakage.
        .withColumn(
            "_latent_supply_stress",
            F.least(
                F.lit(0.98),
                F.greatest(
                    F.lit(0.05),
                    F.lit(0.18)
                    + (F.lit(1.0) - F.col("baseline_ontime_rate")) * F.lit(1.8)
                    + (F.col("contract_lead_time_days") / F.lit(120.0))
                    + F.when(F.col("region").isin("Indo-Pacific", "Alaska/Hawaii", "Central/Southwest Asia"), 0.12).otherwise(0.0)
                    + F.when(F.col("mission_priority") >= 4, 0.06).otherwise(0.0)
                    + F.pmod(F.xxhash64("customer_id", "item_id", F.lit(cfg.seed + 21)), F.lit(250)) / F.lit(1000.0),
                ),
            ),
        )
    )

    bridge_public = relationships.drop(
        "_latent_supply_stress",
        "preferred_supplier_index",
        "customer_index",
        "item_index",
        "item_slot",
        "supported_population",
        "region",
        "policy_min_days_supply",
        "quality_acceptance_rate",
        "baseline_ontime_rate",
        "contract_lead_time_days",
        "unit_cost_usd",
        "criticality",
        "commodity_group",
        "cold_chain_required",
        "mission_priority",
    )

    write_delta(
        bridge_public,
        spark,
        cfg,
        "bridge_customer_item",
        "Active synthetic customer-item supply relationships with preferred supplier and stocking parameters.",
    )

    return {
        "customers": customers,
        "items": items,
        "suppliers": suppliers,
        "relationships_internal": relationships,
    }
