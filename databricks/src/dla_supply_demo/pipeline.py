from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .common import drop_tables, ensure_schema
from .config import GenerationConfig
from .dimensions import build_dimensions
from .facts import build_operational_facts
from .features import build_analytics_and_ml
from .reference_metrics import build_reference_metrics


GENERATED_TABLES = [
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


def generate_all(
    spark: SparkSession,
    cfg: GenerationConfig,
    reset: bool = True,
) -> None:
    """Generate all synthetic managed Delta tables for the DLA medical demo."""
    ensure_schema(spark, cfg)

    if reset:
        drop_tables(spark, cfg, GENERATED_TABLES)

    dimensions = build_dimensions(spark, cfg)

    # Calibrate the generator's hidden stress variable so shortages remain a
    # minority event instead of overwhelming the demo. This latent field is
    # never persisted as a model/agent feature, preventing synthetic leakage.
    dimensions["relationships_internal"] = dimensions[
        "relationships_internal"
    ].withColumn(
        "_latent_supply_stress",
        F.col("_latent_supply_stress") * F.lit(0.33),
    )

    build_operational_facts(spark, cfg, dimensions)
    build_analytics_and_ml(spark, cfg)
    build_reference_metrics(spark, cfg)


def expected_scale(cfg: GenerationConfig):
    p = cfg.profile
    active_pairs = p.customers * p.active_items_per_customer
    return {
        "customer_locations": p.customers,
        "medical_items": p.items,
        "suppliers": p.suppliers,
        "active_customer_item_pairs": active_pairs,
        "daily_inventory_rows": active_pairs * p.history_days,
        "orders": p.orders,
        "supplier_events": p.supplier_events,
        "history_days": p.history_days,
    }
