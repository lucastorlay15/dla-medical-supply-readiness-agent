from datetime import timedelta

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from .common import fq_table, write_delta
from .config import GenerationConfig


def build_analytics_and_ml(spark: SparkSession, cfg: GenerationConfig) -> None:
    inventory = spark.table(fq_table(cfg, "fact_inventory_daily"))
    orders = spark.table(fq_table(cfg, "fact_orders"))
    shipments = spark.table(fq_table(cfg, "fact_shipments"))
    items = spark.table(fq_table(cfg, "dim_medical_item"))
    customers = spark.table(fq_table(cfg, "dim_customer_location"))
    suppliers = spark.table(fq_table(cfg, "dim_supplier"))

    # ------------------------------------------------------------------
    # Point-in-time rolling features for the DataRobot shortage model.
    # The target is NOT random: it is computed from whether the future daily
    # inventory position falls below the operational minimum within 30 days.
    # Rows already below minimum are excluded from training because the model's
    # job is to predict an upcoming shortage, not rediscover a current one.
    # ------------------------------------------------------------------
    pair_order = Window.partitionBy("customer_id", "item_id").orderBy("snapshot_date")
    w7 = pair_order.rowsBetween(-6, 0)
    w30 = pair_order.rowsBetween(-29, 0)
    future30 = pair_order.rowsBetween(1, 30)

    feature_base = (
        inventory
        .withColumn("avg_daily_demand_7d", F.avg("daily_demand_units").over(w7))
        .withColumn("avg_daily_demand_30d", F.avg("daily_demand_units").over(w30))
        .withColumn("demand_stddev_30d", F.stddev_pop("daily_demand_units").over(w30))
        .withColumn("avg_days_of_supply_7d", F.avg("days_of_supply").over(w7))
        .withColumn("min_days_of_supply_30d", F.min("days_of_supply").over(w30))
        .withColumn(
            "future_shortage_flag_30d",
            F.max(
                F.when(F.col("days_of_supply") < F.col("minimum_days_supply"), 1).otherwise(0)
            ).over(future30),
        )
        .withColumn(
            "demand_growth_7_vs_30",
            F.when(
                F.col("avg_daily_demand_30d") > 0,
                F.col("avg_daily_demand_7d") / F.col("avg_daily_demand_30d") - 1.0,
            ).otherwise(0.0),
        )
        .withColumn(
            "demand_cv_30d",
            F.when(
                F.col("avg_daily_demand_30d") > 0,
                F.col("demand_stddev_30d") / F.col("avg_daily_demand_30d"),
            ).otherwise(0.0),
        )
        .withColumn(
            "inventory_gap_days",
            F.col("days_of_supply") - F.col("minimum_days_supply"),
        )
        .withColumn(
            "on_order_coverage_days",
            F.when(
                F.col("avg_daily_demand_30d") > 0,
                F.col("on_order_units") / F.col("avg_daily_demand_30d"),
            ).otherwise(0.0),
        )
        .join(
            items.select(
                "item_id",
                "commodity_group",
                "criticality",
                "unit_cost_usd",
                "cold_chain_required",
                "shelf_life_days",
                "fsc_code",
            ),
            "item_id",
        )
        .join(
            customers.select(
                "customer_id",
                "region",
                "customer_type",
                "service",
                "mission_priority",
                "supported_population",
                "remote_location_flag",
            ),
            "customer_id",
        )
        .join(
            suppliers.select(
                F.col("supplier_id").alias("preferred_supplier_id"),
                F.col("supplier_type"),
                F.col("supplier_region"),
                F.col("contract_lead_time_days"),
                F.col("baseline_ontime_rate"),
                F.col("quality_acceptance_rate"),
                F.col("small_business_flag"),
            ),
            "preferred_supplier_id",
        )
    )

    weekly_sample = (
        F.pmod(
            F.datediff(F.col("snapshot_date"), F.lit(cfg.start_date.isoformat())),
            F.lit(7),
        )
        == 0
    )
    label_cutoff = cfg.as_of_date - timedelta(days=30)

    training = (
        feature_base
        .filter(weekly_sample)
        .filter(F.col("snapshot_date") <= F.lit(label_cutoff.isoformat()))
        .filter(F.col("days_of_supply") >= F.col("minimum_days_supply"))
        .filter(F.col("future_shortage_flag_30d").isNotNull())
        .withColumn("shortage_within_30d", F.col("future_shortage_flag_30d").cast("int"))
        .select(
            "snapshot_date",
            "customer_id",
            "item_id",
            "preferred_supplier_id",
            "commodity_group",
            "criticality",
            "fsc_code",
            "region",
            "customer_type",
            "service",
            "supplier_type",
            "supplier_region",
            "mission_priority",
            "supported_population",
            "remote_location_flag",
            "cold_chain_required",
            "small_business_flag",
            "unit_cost_usd",
            "shelf_life_days",
            F.col("on_hand_units").alias("current_on_hand_units"),
            F.col("on_order_units").alias("current_on_order_units"),
            F.col("backordered_units").alias("current_backordered_units"),
            F.col("expiring_within_90_days_units").alias("current_expiring_90d_units"),
            F.col("days_of_supply").alias("current_days_of_supply"),
            "minimum_days_supply",
            "target_days_supply",
            "inventory_gap_days",
            "avg_daily_demand_7d",
            "avg_daily_demand_30d",
            "demand_growth_7_vs_30",
            "demand_cv_30d",
            "avg_days_of_supply_7d",
            "min_days_of_supply_30d",
            "on_order_coverage_days",
            "contract_lead_time_days",
            "baseline_ontime_rate",
            "quality_acceptance_rate",
            "shortage_within_30d",
        )
    )

    write_delta(
        training,
        spark,
        cfg,
        "ml_shortage_training",
        "Point-in-time weekly training set for predicting whether an in-stock customer-item pair will fall below its minimum days of supply within 30 days.",
    )

    scoring = (
        feature_base
        .filter(F.col("snapshot_date") == F.lit(cfg.as_of_date.isoformat()))
        .withColumn(
            "currently_below_minimum",
            F.col("days_of_supply") < F.col("minimum_days_supply"),
        )
        .select(
            "snapshot_date",
            "customer_id",
            "item_id",
            "preferred_supplier_id",
            "commodity_group",
            "criticality",
            "fsc_code",
            "region",
            "customer_type",
            "service",
            "supplier_type",
            "supplier_region",
            "mission_priority",
            "supported_population",
            "remote_location_flag",
            "cold_chain_required",
            "small_business_flag",
            "unit_cost_usd",
            "shelf_life_days",
            F.col("on_hand_units").alias("current_on_hand_units"),
            F.col("on_order_units").alias("current_on_order_units"),
            F.col("backordered_units").alias("current_backordered_units"),
            F.col("expiring_within_90_days_units").alias("current_expiring_90d_units"),
            F.col("days_of_supply").alias("current_days_of_supply"),
            "minimum_days_supply",
            "target_days_supply",
            "inventory_gap_days",
            "avg_daily_demand_7d",
            "avg_daily_demand_30d",
            "demand_growth_7_vs_30",
            "demand_cv_30d",
            "avg_days_of_supply_7d",
            "min_days_of_supply_30d",
            "on_order_coverage_days",
            "contract_lead_time_days",
            "baseline_ontime_rate",
            "quality_acceptance_rate",
            "currently_below_minimum",
        )
    )

    write_delta(
        scoring,
        spark,
        cfg,
        "ml_shortage_scoring",
        "Current-date feature set to batch score with the DataRobot 30-day medical supply shortage model.",
    )

    # ------------------------------------------------------------------
    # Supplier performance: simple, explainable aggregates the SQL tool can
    # use when the user asks why an item is risky.
    # ------------------------------------------------------------------
    perf_start = cfg.as_of_date - timedelta(days=90)
    supplier_performance = (
        shipments
        .filter(F.col("ship_date") >= F.lit(perf_start.isoformat()))
        .groupBy("supplier_id")
        .agg(
            F.count("shipment_id").alias("shipments_90d"),
            F.round(F.avg(F.col("on_time_flag").cast("double")), 4).alias("actual_ontime_rate_90d"),
            F.round(F.avg("days_late"), 2).alias("avg_days_late_90d"),
            F.max("days_late").alias("max_days_late_90d"),
            F.sum(F.when(F.col("shipment_status") == "LATE", 1).otherwise(0)).alias("late_shipments_90d"),
        )
        .join(
            suppliers.select(
                "supplier_id",
                "supplier_name",
                "supplier_region",
                "supplier_type",
                "contract_lead_time_days",
                "baseline_ontime_rate",
            ),
            "supplier_id",
        )
    )

    write_delta(
        supplier_performance,
        spark,
        cfg,
        "analytics_supplier_performance",
        "Current 90-day supplier delivery performance for SQL-based root-cause analysis.",
    )

    # ------------------------------------------------------------------
    # Agent-ready current position. This deliberately contains operational
    # evidence, not a model prediction. Tool 3 will add DataRobot risk scores.
    # ------------------------------------------------------------------
    late_orders = (
        orders
        .filter(F.col("order_status") == "BACKORDERED")
        .groupBy("customer_id", "item_id")
        .agg(
            F.count("order_id").alias("backordered_orders"),
            F.sum(F.col("ordered_units") - F.col("delivered_units")).alias("late_inbound_units"),
            F.min("promised_delivery_date").alias("oldest_missed_promise_date"),
        )
    )

    current_inventory = inventory.filter(
        F.col("snapshot_date") == F.lit(cfg.as_of_date.isoformat())
    )

    current_position = (
        current_inventory
        .join(
            items.select(
                "item_id",
                "item_name",
                "commodity_group",
                "criticality",
                "fsc_code",
                "unit_cost_usd",
                "cold_chain_required",
                "policy_reference_id",
            ),
            "item_id",
        )
        .join(
            customers.select(
                "customer_id",
                "customer_name",
                "region",
                "customer_type",
                "service",
                "mission_priority",
                "supported_population",
            ),
            "customer_id",
        )
        .join(
            supplier_performance.select(
                "supplier_id",
                "supplier_name",
                "supplier_region",
                "supplier_type",
                "contract_lead_time_days",
                "actual_ontime_rate_90d",
                "avg_days_late_90d",
                "late_shipments_90d",
            ),
            F.col("preferred_supplier_id") == F.col("supplier_id"),
            "left",
        )
        .drop("supplier_id")
        .join(late_orders, ["customer_id", "item_id"], "left")
        .fillna(
            {
                "backordered_orders": 0,
                "late_inbound_units": 0,
                "late_shipments_90d": 0,
            }
        )
        .withColumn(
            "days_above_minimum",
            F.round(F.col("days_of_supply") - F.col("minimum_days_supply"), 2),
        )
        .withColumn(
            "estimated_stockout_date_at_current_demand",
            F.date_add("snapshot_date", F.ceil("days_of_supply").cast("int")),
        )
        .select(
            "snapshot_date",
            "customer_id",
            "customer_name",
            "region",
            "customer_type",
            "service",
            "mission_priority",
            "supported_population",
            "item_id",
            "item_name",
            "commodity_group",
            "fsc_code",
            "criticality",
            "policy_reference_id",
            "cold_chain_required",
            "unit_cost_usd",
            "preferred_supplier_id",
            "supplier_name",
            "supplier_region",
            "supplier_type",
            "daily_demand_units",
            "on_hand_units",
            "on_order_units",
            "backordered_units",
            "days_of_supply",
            "minimum_days_supply",
            "target_days_supply",
            "days_above_minimum",
            "inventory_status",
            "inventory_value_usd",
            "backordered_orders",
            "late_inbound_units",
            "oldest_missed_promise_date",
            "contract_lead_time_days",
            "actual_ontime_rate_90d",
            "avg_days_late_90d",
            "late_shipments_90d",
            "estimated_stockout_date_at_current_demand",
        )
    )

    write_delta(
        current_position,
        spark,
        cfg,
        "agent_current_supply_position",
        "Agent-ready current medical supply position combining inventory, customer, item, supplier, and late-order evidence without model predictions.",
    )
