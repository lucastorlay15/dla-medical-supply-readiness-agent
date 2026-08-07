import math
from typing import Dict

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from .common import write_delta
from .config import GenerationConfig


def _hash_fraction(*cols, modulus: int = 10_000):
    return F.pmod(F.xxhash64(*cols), F.lit(modulus)) / F.lit(float(modulus))


def build_operational_facts(
    spark: SparkSession,
    cfg: GenerationConfig,
    dimensions: Dict[str, DataFrame],
) -> Dict[str, DataFrame]:
    p = cfg.profile
    relationships = dimensions["relationships_internal"]
    suppliers = dimensions["suppliers"]

    # ------------------------------------------------------------------
    # Daily inventory / demand position
    # ------------------------------------------------------------------
    dates = (
        spark.range(p.history_days)
        .withColumnRenamed("id", "day_index")
        .withColumn(
            "snapshot_date",
            F.date_add(F.lit(cfg.start_date.isoformat()), F.col("day_index").cast("int")),
        )
    )

    inventory = relationships.crossJoin(dates)

    pair_phase = F.pmod(
        F.xxhash64("customer_id", "item_id", F.lit(cfg.seed + 100)), F.lit(180)
    )
    cycle_day = F.pmod(F.col("day_index") + pair_phase, F.lit(180)).cast("double")
    supply_episode = F.greatest(
        F.lit(0.0),
        F.sin(cycle_day / F.lit(180.0) * F.lit(2.0 * math.pi)),
    )
    days_before_as_of = F.datediff(F.lit(cfg.as_of_date.isoformat()), F.col("snapshot_date"))
    current_pressure = F.greatest(
        F.lit(0.0),
        F.lit(1.0) - (days_before_as_of.cast("double") / F.lit(90.0)),
    )
    seasonal = (
        F.lit(1.0)
        + F.lit(0.08)
        * F.sin(
            F.dayofyear("snapshot_date").cast("double")
            / F.lit(365.25)
            * F.lit(2.0 * math.pi)
        )
    )
    demand_noise = _hash_fraction(
        "customer_id", "item_id", "snapshot_date", F.lit(cfg.seed + 101)
    ) - F.lit(0.5)
    inventory_noise = _hash_fraction(
        "customer_id", "item_id", "snapshot_date", F.lit(cfg.seed + 102)
    ) - F.lit(0.5)

    inventory = (
        inventory
        .withColumn(
            "daily_demand_units",
            F.greatest(
                F.lit(0.1),
                F.round(
                    F.col("baseline_daily_demand")
                    * seasonal
                    * (
                        F.lit(1.0)
                        + F.lit(0.34) * F.col("_latent_supply_stress") * supply_episode
                        + F.lit(0.30) * F.col("_latent_supply_stress") * current_pressure
                    )
                    * (F.lit(1.0) + demand_noise * F.lit(0.18)),
                    2,
                ),
            ),
        )
        .withColumn(
            "days_of_supply",
            F.greatest(
                F.lit(0.0),
                F.round(
                    F.col("target_days_supply").cast("double")
                    - F.lit(23.0) * F.col("_latent_supply_stress") * supply_episode
                    - F.lit(25.0) * F.col("_latent_supply_stress") * current_pressure
                    + inventory_noise * F.lit(5.0),
                    2,
                ),
            ),
        )
        .withColumn(
            "on_hand_units",
            F.greatest(
                F.lit(0),
                F.round(F.col("daily_demand_units") * F.col("days_of_supply")).cast("long"),
            ),
        )
        .withColumn(
            "on_order_units",
            F.greatest(
                F.lit(0),
                F.round(
                    F.col("daily_demand_units")
                    * F.col("contract_lead_time_days")
                    * (
                        F.lit(0.55)
                        + F.col("_latent_supply_stress") * F.lit(0.65)
                        + F.when(F.col("days_of_supply") < F.col("minimum_days_supply") + 7, 0.45).otherwise(0.0)
                    )
                ).cast("long"),
            ),
        )
        .withColumn(
            "backordered_units",
            F.when(
                F.col("days_of_supply") < F.col("minimum_days_supply") + 4,
                F.round(
                    F.col("daily_demand_units")
                    * (F.col("minimum_days_supply") + 6 - F.col("days_of_supply"))
                    * F.lit(0.35)
                ).cast("long"),
            ).otherwise(F.lit(0).cast("long")),
        )
        .withColumn(
            "expiring_within_90_days_units",
            F.when(
                F.col("cold_chain_required"),
                F.round(
                    F.col("on_hand_units")
                    * _hash_fraction(
                        "customer_id", "item_id", "snapshot_date", F.lit(cfg.seed + 103)
                    )
                    * F.lit(0.08)
                ).cast("long"),
            ).otherwise(F.lit(0).cast("long")),
        )
        .withColumn(
            "inventory_status",
            F.when(F.col("on_hand_units") <= 0, "STOCKOUT")
            .when(F.col("days_of_supply") < F.col("minimum_days_supply"), "BELOW_MINIMUM")
            .when(F.col("days_of_supply") < F.col("minimum_days_supply") + 7, "WATCH")
            .otherwise("HEALTHY"),
        )
        .withColumn(
            "inventory_value_usd",
            F.round(F.col("on_hand_units") * F.col("unit_cost_usd"), 2),
        )
        .withColumn("snapshot_month", F.trunc("snapshot_date", "month"))
        .select(
            "snapshot_date",
            "snapshot_month",
            "customer_id",
            "item_id",
            "preferred_supplier_id",
            "daily_demand_units",
            "on_hand_units",
            "on_order_units",
            "backordered_units",
            "expiring_within_90_days_units",
            "days_of_supply",
            "minimum_days_supply",
            "target_days_supply",
            "inventory_status",
            "inventory_value_usd",
        )
    )

    write_delta(
        inventory,
        spark,
        cfg,
        "fact_inventory_daily",
        "Daily synthetic inventory and demand position by customer location and medical item.",
        partition_by=("snapshot_month",),
    )

    # ------------------------------------------------------------------
    # Orders / requisitions. Orders map onto the same customer-item
    # relationships so demand, supplier behavior, and shortage pressure are
    # correlated rather than independent random tables.
    # ------------------------------------------------------------------
    order_base = (
        spark.range(p.orders)
        .withColumnRenamed("id", "order_index")
        .withColumn("order_id", F.format_string("ORD-%010d", F.col("order_index") + 1))
        .withColumn(
            "customer_index",
            F.pmod(F.col("order_index") * 17 + 5, F.lit(p.customers)).cast("long"),
        )
        .withColumn("customer_id", F.format_string("CUST-%05d", F.col("customer_index") + 1))
        .withColumn(
            "item_slot",
            F.pmod(F.col("order_index") * 29 + 11, F.lit(p.active_items_per_customer)).cast("long"),
        )
        .withColumn(
            "order_day_index",
            F.pmod(
                F.xxhash64("order_index", F.lit(cfg.seed + 110)), F.lit(p.history_days)
            ).cast("int"),
        )
        .withColumn(
            "order_date",
            F.date_add(F.lit(cfg.start_date.isoformat()), F.col("order_day_index")),
        )
        .join(
            relationships.select(
                "customer_id",
                "item_slot",
                "item_id",
                "preferred_supplier_id",
                "baseline_daily_demand",
                "_latent_supply_stress",
                "mission_priority",
                "criticality",
                "unit_cost_usd",
            ),
            ["customer_id", "item_slot"],
        )
        .join(
            suppliers.select(
                "supplier_id",
                "contract_lead_time_days",
                "baseline_ontime_rate",
            ),
            F.col("preferred_supplier_id") == F.col("supplier_id"),
        )
        .drop("supplier_id")
    )

    qty_noise = _hash_fraction("order_id", F.lit(cfg.seed + 111))
    delivery_noise = _hash_fraction("order_id", F.lit(cfg.seed + 112))
    cancel_noise = _hash_fraction("order_id", F.lit(cfg.seed + 113))
    handling_days = (
        F.lit(1)
        + F.pmod(F.xxhash64("order_id", F.lit(cfg.seed + 114)), F.lit(4)).cast("int")
    )
    delay_probability = F.least(
        F.lit(0.70),
        (F.lit(1.0) - F.col("baseline_ontime_rate"))
        + F.col("_latent_supply_stress") * F.lit(0.18),
    )
    delay_days = F.when(
        delivery_noise < delay_probability,
        F.ceil(
            F.lit(2.0)
            + F.col("_latent_supply_stress") * F.lit(24.0)
            + delivery_noise * F.lit(18.0)
        ).cast("int"),
    ).otherwise((F.floor(delivery_noise * F.lit(4.0)) - F.lit(2)).cast("int"))

    orders_enriched = (
        order_base
        .withColumn(
            "ordered_units",
            F.greatest(
                F.lit(1),
                F.ceil(
                    F.col("baseline_daily_demand")
                    * (F.lit(7.0) + qty_noise * F.lit(28.0))
                    * (F.lit(1.0) + F.col("_latent_supply_stress") * F.lit(0.35))
                ).cast("long"),
            ),
        )
        .withColumn(
            "order_priority",
            F.when(
                (F.col("criticality") == "MISSION_CRITICAL") | (F.col("mission_priority") >= 5),
                "URGENT",
            )
            .when((F.col("criticality") == "HIGH") | (F.col("mission_priority") >= 4), "HIGH")
            .otherwise("ROUTINE"),
        )
        .withColumn(
            "promised_delivery_date",
            F.date_add("order_date", F.col("contract_lead_time_days")),
        )
        .withColumn("ship_date", F.date_add("order_date", handling_days))
        .withColumn("delay_days", delay_days)
        .withColumn(
            "actual_delivery_date",
            F.date_add("promised_delivery_date", F.col("delay_days")),
        )
        .withColumn(
            "order_status",
            F.when(cancel_noise < F.lit(0.005), "CANCELLED")
            .when(F.col("actual_delivery_date") <= F.lit(cfg.as_of_date.isoformat()), "DELIVERED")
            .when(F.col("promised_delivery_date") < F.lit(cfg.as_of_date.isoformat()), "BACKORDERED")
            .when(F.col("ship_date") <= F.lit(cfg.as_of_date.isoformat()), "IN_TRANSIT")
            .otherwise("OPEN"),
        )
        .withColumn(
            "delivered_units",
            F.when(
                F.col("order_status") == "DELIVERED",
                F.round(
                    F.col("ordered_units")
                    * F.when(delivery_noise < F.lit(0.04), F.lit(0.75)).otherwise(F.lit(1.0))
                ).cast("long"),
            ).otherwise(F.lit(0).cast("long")),
        )
        .withColumn(
            "extended_value_usd",
            F.round(F.col("ordered_units") * F.col("unit_cost_usd"), 2),
        )
        .withColumn("order_month", F.trunc("order_date", "month"))
    )

    orders = orders_enriched.select(
        "order_id",
        "order_date",
        "order_month",
        "customer_id",
        "item_id",
        "preferred_supplier_id",
        "order_priority",
        "ordered_units",
        "delivered_units",
        "order_status",
        "promised_delivery_date",
        "extended_value_usd",
    )

    write_delta(
        orders,
        spark,
        cfg,
        "fact_orders",
        "Synthetic medical supply requisitions/orders including priority, quantity, status, promised delivery, and value.",
        partition_by=("order_month",),
    )

    shipments = (
        orders_enriched
        .filter(F.col("order_status") != "CANCELLED")
        .withColumn("shipment_id", F.concat(F.lit("SHP-"), F.substring("order_id", 5, 20)))
        .withColumn(
            "shipment_status",
            F.when(F.col("actual_delivery_date") <= F.lit(cfg.as_of_date.isoformat()), "DELIVERED")
            .when(F.col("promised_delivery_date") < F.lit(cfg.as_of_date.isoformat()), "LATE")
            .otherwise("IN_TRANSIT"),
        )
        .withColumn("days_late", F.greatest(F.lit(0), F.col("delay_days")))
        .withColumn("on_time_flag", F.col("delay_days") <= 0)
        .withColumn("ship_month", F.trunc("ship_date", "month"))
        .select(
            "shipment_id",
            "order_id",
            "ship_date",
            "ship_month",
            "customer_id",
            "item_id",
            F.col("preferred_supplier_id").alias("supplier_id"),
            "promised_delivery_date",
            F.when(
                F.col("actual_delivery_date") <= F.lit(cfg.as_of_date.isoformat()),
                F.col("actual_delivery_date"),
            ).alias("actual_delivery_date"),
            "shipment_status",
            "days_late",
            "on_time_flag",
            F.col("ordered_units").alias("shipped_units"),
        )
    )

    write_delta(
        shipments,
        spark,
        cfg,
        "fact_shipments",
        "Synthetic shipment history used to analyze supplier delivery performance and late inbound material.",
        partition_by=("ship_month",),
    )

    # ------------------------------------------------------------------
    # Supplier disruption events: interpretable operational context for SQL
    # analysis and later what-if/action tools.
    # ------------------------------------------------------------------
    event_types = [
        "MANUFACTURING_CONSTRAINT",
        "TRANSPORT_DELAY",
        "QUALITY_HOLD",
        "COLD_CHAIN_EXCEPTION",
        "RAW_MATERIAL_SHORTAGE",
        "CAPACITY_REDUCTION",
    ]
    events = (
        spark.range(p.supplier_events)
        .withColumnRenamed("id", "event_index")
        .withColumn("event_id", F.format_string("EVT-%05d", F.col("event_index") + 1))
        .withColumn(
            "supplier_index",
            F.pmod(F.col("event_index") * 31 + 7, F.lit(p.suppliers)).cast("long"),
        )
        .join(suppliers.select("supplier_index", "supplier_id"), "supplier_index")
        .withColumn(
            "event_type",
            F.element_at(
                F.array(*[F.lit(x) for x in event_types]),
                F.pmod(F.col("event_index") * 5 + 1, F.lit(len(event_types))).cast("int") + 1,
            ),
        )
        .withColumn(
            "start_day_index",
            F.pmod(
                F.xxhash64("event_index", F.lit(cfg.seed + 120)),
                F.lit(max(1, p.history_days - 45)),
            ).cast("int"),
        )
        .withColumn(
            "start_date",
            F.date_add(F.lit(cfg.start_date.isoformat()), F.col("start_day_index")),
        )
        .withColumn(
            "duration_days",
            (F.lit(5) + F.pmod(F.xxhash64("event_id"), F.lit(36))).cast("int"),
        )
        .withColumn("end_date", F.date_add("start_date", F.col("duration_days")))
        .withColumn(
            "severity",
            F.when(F.pmod(F.xxhash64("event_id", F.lit(1)), F.lit(100)) < 18, "SEVERE")
            .when(F.pmod(F.xxhash64("event_id", F.lit(1)), F.lit(100)) < 55, "MODERATE")
            .otherwise("LOW"),
        )
        .withColumn(
            "description",
            F.concat(
                F.lit("Synthetic "),
                F.lower(F.regexp_replace("event_type", "_", " ")),
                F.lit(" affecting expected supplier lead time."),
            ),
        )
        .select(
            "event_id",
            "supplier_id",
            "event_type",
            "severity",
            "start_date",
            "end_date",
            "duration_days",
            "description",
        )
    )

    write_delta(
        events,
        spark,
        cfg,
        "fact_supplier_events",
        "Synthetic supplier disruption events for explaining elevated medical supply risk.",
    )

    return {
        "inventory": inventory,
        "orders": orders,
        "shipments": shipments,
        "supplier_events": events,
    }
