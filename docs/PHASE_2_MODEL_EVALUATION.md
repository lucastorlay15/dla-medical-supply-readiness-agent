# Phase 2 — Model Evaluation and Synthetic Distribution-Drift Finding

## Status

The first DataRobot modeling run successfully demonstrated that the synthetic feature set contains strong predictive signal for 30-day shortage risk. Historical backtests showed excellent discrimination, but the latest holdout degraded sharply.

The primary Phase 2 problem is now understood to be **artificial distribution drift introduced by the synthetic data generator**, not a lack of predictive signal in the model.

## Initial model finding

The first set of DataRobot classification models showed:

- **Excellent to exceptional discrimination** on historical backtests.
- PR AUC values approximately **0.40–0.50** for a rare-event target.
- ROC AUC values approximately **0.80–0.96**.
- LogLoss around **0.13** on the initial model runs.
- Severe degradation on the latest holdout.

The initial metric story can be summarized as:

> **The initial model had excellent ranking performance but poor probability calibration. Investigation also exposed an artificial distribution shift in the synthetic data.**

The ranking results demonstrate that the generated operational features contain meaningful shortage signal. However, literal probabilities should not be exposed to the agent until the time distribution is corrected and calibration is re-evaluated on the corrected dataset.

## Root cause: synthetic distribution drift

The synthetic data generator contains a one-time `current_pressure` ramp tied directly to the configured as-of date. During approximately the final 90 days of the generated history, that term progressively:

- increases synthetic demand, and
- reduces synthetic days of supply.

Because this pressure exists only near the end of the timeline, the latest period is structurally different from the historical periods used to train the model.

Observed monthly shortage prevalence illustrates the shift:

- historical months: approximately 1% shortage prevalence,
- April 2026: ~1.47%,
- May 2026: ~5.95%,
- June 2026: ~13.9%,
- July 2026: ~20.6%.

This creates an artificial late-history regime change precisely where the time-aware holdout is located. The holdout therefore tests the model on a synthetic condition that does not have a comparable historical training distribution.

## Why this matters to the agent

Tool 3 is intended to support statements such as:

> "This item/location pair has an 82% probability of falling below minimum stock within the next 30 days."

That requires both:

1. strong discrimination, so the model correctly separates higher- and lower-risk positions, and
2. acceptable probability calibration, so a predicted value such as `0.82` can be interpreted as an approximately 82% empirical probability.

The current models satisfy the first requirement. The second should be re-evaluated only after removing the artificial distribution drift.

## Corrective decision

The project will preserve the current business question, target, table design, feature set, and overall synthetic supply-chain logic.

The synthetic data generator will be changed narrowly to remove the one-time as-of-date pressure ramp and any equivalent non-repeating late-history behavior. The recurring supply-pressure cycle, annual seasonality, supplier/customer differences, and deterministic random variation will remain so the data continues to contain realistic operational variation without a structural end-of-history shift.

After regeneration:

1. Verify monthly shortage prevalence is reasonably stationary rather than sharply increasing near the as-of date.
2. Verify current inventory, days-of-supply, demand, orders, and shortage examples remain operationally realistic.
3. Retrain the DataRobot classification models using the same target and time-aware validation approach.
4. Re-evaluate PR AUC and ROC AUC for discrimination.
5. Re-evaluate LogLoss and probability calibration separately.
6. Apply model calibration/post-processing only if the corrected data still produces strong discrimination with imperfect probability calibration.
7. Expose literal probabilities to Tool 3 only after calibration is acceptable.

## Desired final modeling story

> **"The initial model had excellent ranking performance but poor probability calibration. Investigation also exposed an artificial distribution shift in the synthetic data. I corrected the data-generating process so the current stress regime had historical analogues, retrained the model, and then evaluated calibration separately before exposing probabilities to the agent."**

## Phase 2 success condition

The final model does not need perfect prediction. It should provide:

- strong rare-event discrimination,
- stable performance across chronological backtests and holdout,
- plausible operational feature drivers,
- probabilities that are sufficiently calibrated to support the agent's 30-day shortage-risk statements,
- no future or synthetic-leakage fields.
