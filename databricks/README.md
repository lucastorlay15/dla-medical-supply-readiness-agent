# Databricks synthetic data layer

This folder generates the structured data used by the DLA Medical Supply Readiness Agent demo.

## Goal

The data is designed backward from the core decision question:

> Which critical medical supplies are at risk of shortage over the next 30 days, where will those shortages occur, why, and what should we do about them?

The generator supports three MVP capabilities:

1. **SQL / operational data tool** — aggregate and investigate large structured Delta tables.
2. **Policy/RAG tool** — use `policy_reference_id` and operational facts to ground policy retrieval.
3. **DataRobot shortage-risk model** — predict `shortage_within_30d` from point-in-time operational features.

Tools planned for the broader production story, but not required for the MVP, are scenario simulation and human-approved action creation.

## Run it

Open `notebooks/00_generate_all.py` as a Databricks notebook from the Git folder and run all cells.

Parameters:

- `scale`: `tiny`, `demo`, or `large`. Start with `tiny`, then use `demo`.
- `catalog_name`: leave blank to register objects in the current/default catalog.
- `schema_name`: defaults to `dla_medical_supply_demo`.
- `as_of_date`: defaults to the notebook run date.
- `reset`: drops/recreates only this project's generated tables.

The notebook resolves the catalog with `spark.catalog.currentCatalog()` when no override is supplied, creates the schema if necessary, and writes **managed Delta tables** with `saveAsTable`.

## Generated Delta tables

### Operational dimensions

- `dim_customer_location` — synthetic receiving/customer locations, region, service, mission priority, supported population.
- `dim_medical_item` — synthetic medical items, DLA-like commodity groups/FSC codes, criticality, cost, cold-chain flag, stock policy reference.
- `dim_supplier` — synthetic manufacturers/prime vendors/distributors with lead-time and reliability characteristics.
- `bridge_customer_item` — active customer-item relationships, preferred supplier, baseline demand, minimum and target days of supply.

### Operational facts

- `fact_inventory_daily` — daily customer-item inventory position and demand. This is the primary high-volume table.
- `fact_orders` — requisitions/orders with priority, quantity, status, promised delivery, and value.
- `fact_shipments` — shipment/delivery history used for supplier performance and late-material analysis.
- `fact_supplier_events` — interpretable disruption events such as manufacturing constraints, quality holds, and transportation delays.

### Agent / analytics tables

- `agent_current_supply_position` — current joined operational position intended for the SQL tool. It contains evidence, not model predictions.
- `analytics_supplier_performance` — current 90-day supplier delivery performance.

### DataRobot model tables

- `ml_shortage_training` — weekly point-in-time training examples. Target: `shortage_within_30d`.
- `ml_shortage_scoring` — current-date feature rows for batch scoring.

The training target is derived from the next 30 days of inventory history. Rows already below their minimum stock level are excluded from training, because the objective is to predict an **upcoming** shortage.

### Public scale/provenance

- `reference_enterprise_metrics` — official public DLA scale figures and source URLs. These are deliberately separate from all synthetic operational records.

## Recommended demo scale

The `demo` profile generates roughly:

- 120 synthetic customer locations
- 500 synthetic medical items
- 120 synthetic suppliers
- 12,000 active customer-item relationships
- 540 days of history
- **6.48 million daily inventory rows**
- 500,000 orders

This is intentionally smaller than real DLA enterprise scale. The point of the MVP is to demonstrate the same Spark/Delta aggregation pattern without wasting interview-trial resources trying to reproduce tens of millions of annual orders or a multi-terabyte production estate.

## Why the data is structured this way

Shortages are not assigned randomly. A hidden synthetic stress process influences demand, days of supply, shipment delay, and backorders. That latent generator variable is never persisted as an agent/model feature. The DataRobot model must instead learn from observable signals such as:

- current days of supply vs. minimum
- recent demand level and growth
- demand volatility
- on-order coverage
- backordered units
- supplier lead time
- supplier on-time performance
- item criticality
- customer mission priority and region
- cold-chain requirements

This makes the demo useful for both predictive modeling and explainable agent investigation.
