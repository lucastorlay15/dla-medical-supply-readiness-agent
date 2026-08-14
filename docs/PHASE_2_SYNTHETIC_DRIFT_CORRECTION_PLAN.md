# Phase 2 — Synthetic Distribution-Drift Correction Plan

## Goal

Remove the artificial late-history distribution shift from the synthetic data generator while preserving realistic medical supply behavior, class imbalance, and learnable shortage-risk signal.

The intent is a **narrow correction**, not a redesign of the synthetic supply-chain model.

## Root cause in code

`databricks/src/dla_supply_demo/facts.py` currently creates a `current_pressure` term based on distance from the configured as-of date:

```python
days_before_as_of = F.datediff(F.lit(cfg.as_of_date.isoformat()), F.col("snapshot_date"))
current_pressure = F.greatest(
    F.lit(0.0),
    F.lit(1.0) - (days_before_as_of.cast("double") / F.lit(90.0)),
)
```

That term is then used in two places:

1. to increase daily demand near the end of the timeline, and
2. to reduce days of supply near the end of the timeline.

Because the effect exists only in the final ~90 days, the generated data develops an artificial end-of-history regime that is not represented earlier in training history.

## Code-change plan

### 1. Remove the as-of-date pressure ramp

Delete the `days_before_as_of` / `current_pressure` calculation from `facts.py`.

Remove the following contribution from `daily_demand_units`:

```python
+ 0.30 * _latent_supply_stress * current_pressure
```

Remove the following contribution from `days_of_supply`:

```python
- 25.0 * _latent_supply_stress * current_pressure
```

### 2. Preserve stationary/repeating supply behavior

Keep the existing mechanisms that do not create one-way time drift:

- pair-specific 180-day `supply_episode` cycles,
- annual demand seasonality,
- customer/item latent supply stress,
- supplier reliability and lead-time differences,
- deterministic daily demand/inventory noise,
- existing minimum/target days-of-supply logic,
- order and shipment generation.

These mechanisms create cross-sectional and temporal variation while repeating over history instead of making the latest period uniquely difficult.

### 3. Do not retune coefficients immediately

The first corrected generation run should use the existing coefficients for the recurring `supply_episode` term.

Reason: removing `current_pressure` is the minimum causal fix. Retuning multiple coefficients at the same time would make it harder to know whether the drift correction alone solved the problem.

Only tune the remaining recurring-stress coefficients if the regenerated data becomes operationally implausible or produces too few shortage examples for modeling.

## Validation after regeneration

Run the `demo` profile again with the same fixed as-of date and seed.

Validate four things before reconnecting DataRobot:

### A. Monthly target stability

The monthly `shortage_within_30d` rate should no longer rise monotonically into the final months.

Desired behavior:

- shortage remains a minority event,
- some month-to-month movement is expected,
- no unique 5% → 14% → 20% end-of-history ramp,
- historical and later periods should occupy comparable ranges.

### B. Current supply realism

The as-of-date population should still include a useful mix of:

- HEALTHY,
- WATCH,
- BELOW_MINIMUM / STOCKOUT where appropriate,
- customer-item positions near but above their minimum threshold.

The current scoring table should still contain enough meaningful high-risk positions for the live demo.

### C. Feature realism

Confirm that core model features retain plausible distributions and relationships:

- current days of supply,
- inventory gap days,
- recent demand growth,
- on-order coverage,
- supplier lead time,
- supplier baseline on-time rate.

Future-shortage rows should remain distinguishable from non-shortage rows without requiring any hidden future information.

### D. No residual time drift

Compare early, middle, and late historical windows for:

- shortage prevalence,
- average days of supply,
- inventory gap,
- demand growth,
- positive-class feature distributions.

The goal is not perfect statistical stationarity; realistic seasonality is allowed. The goal is to eliminate a structural late-history regime created solely by the generator's proximity to `as_of_date`.

## DataRobot retraining plan

After the corrected data passes validation:

1. Refresh/re-import `ml_shortage_training` in DataRobot.
2. Use the same `shortage_within_30d` target.
3. Keep the same time-aware partitioning and 30-day label gap.
4. Retrain classification candidates.
5. Select models using both discrimination and probability quality:
   - PR AUC,
   - ROC AUC,
   - LogLoss,
   - calibration behavior.
6. Confirm performance is stable across chronological backtests and holdout.
7. If ranking remains strong but probabilities are still miscalibrated, add calibration/post-processing to the selected model.
8. Batch-score `ml_shortage_scoring` only after literal probabilities are credible enough for Tool 3.

## What will not change

This correction does **not** change:

- the million-dollar question,
- the 30-day shortage target,
- the unit of analysis,
- the DataRobot classification approach,
- Databricks table names,
- Tool 1 / Tool 2 / Tool 3 architecture,
- the distinction between observed operational evidence and model prediction.

## Final desired story

> **The initial model had excellent ranking performance but poor probability calibration. Investigation also exposed an artificial distribution shift in the synthetic data. I corrected the data-generating process so the current stress regime had historical analogues, retrained the model, and then evaluated calibration separately before exposing probabilities to the agent.**
