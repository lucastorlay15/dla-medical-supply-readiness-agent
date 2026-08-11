# Phase 2 — Model Evaluation and Calibration Finding

## Status

The first DataRobot modeling run successfully demonstrated that the synthetic feature set contains strong predictive signal for 30-day shortage risk, but it also exposed a probability-calibration problem that must be resolved before Tool 3 can safely present literal shortage probabilities.

## Initial finding

The first set of DataRobot classification models showed:

- **Excellent to exceptional discrimination** on historical backtests.
- PR AUC values approximately **0.40–0.50** for a rare-event target.
- ROC AUC values approximately **0.80–0.96**.
- LogLoss around **0.13**, materially worse than a constant-probability baseline on the observed Backtest 1 prevalence.

The working interpretation is:

> **The model has excellent discrimination but poor calibration.**

In practical terms, the models are very good at ranking which item/location pairs are more likely to experience a shortage, but their raw probability values should not yet be interpreted as trustworthy literal probabilities.

## Why this matters to the agent

The intended shortage-risk tool was designed to answer questions such as:

> "This item/location pair has an 82% probability of falling below minimum stock within the next 30 days."

That statement requires **calibrated probabilities**, not merely strong ranking performance.

A model with strong PR AUC and ROC AUC can still assign probabilities that are systematically too high or too low. For the live agent, presenting those raw values as literal probabilities would overstate model certainty.

## Synthetic late-period shift

A separate issue was identified in the synthetic data generator. The final part of the generated timeline includes a one-time `current_pressure` ramp that increases demand and reduces days of supply near the synthetic as-of date.

This produces a sharp increase in shortage prevalence late in the history:

- historical months: approximately 1% shortage prevalence,
- April 2026: ~1.47%,
- May 2026: ~5.95%,
- June 2026: ~13.9%,
- July 2026: ~20.6%.

This explains the severe degradation observed on the latest holdout and means that a calibration learned only from the historically stable period may not remain valid in the artificially shifted final regime.

## Decision rule

The project should distinguish two modeling requirements:

1. **Discrimination / ranking** — identify which supplies are most at risk. The current models already demonstrate strong performance here.
2. **Calibration** — ensure a predicted value such as `0.82` can be communicated as an approximately 82% empirical probability. This requirement is not yet satisfied.

## Preferred path

To preserve the original probability-based Tool 3 design, the preferred final model should:

1. Retain the current predictive feature set and classification target.
2. Remove or redesign the one-time late-history synthetic pressure shift so comparable stress episodes exist in historical training data.
3. Retrain the strongest DataRobot model.
4. Apply a calibration/post-processing step to the selected model if needed.
5. Re-evaluate LogLoss alongside PR AUC and ROC AUC.
6. Use literal probability language in the agent only after calibration is acceptable.

## Fallback path without regenerating data

If the synthetic data is not regenerated, Tool 3 should be framed as a **relative shortage-risk ranking** rather than a literal probability estimator.

The agent can safely return:

- ranked at-risk item/location pairs,
- relative risk scores,
- risk tiers such as Critical / High / Moderate / Low,
- model drivers and operational evidence.

In that version, avoid statements such as "82% probability" unless the score has been separately calibrated.

The million-dollar question can remain largely unchanged:

> **Which critical medical supplies are at greatest risk of shortage over the next 30 days, where will those shortages occur, why, and what should we do about them?**

The phrase **"at greatest risk"** emphasizes ranking and prioritization rather than requiring the raw model score to be a perfectly calibrated probability.

## Interview takeaway

This modeling iteration is a useful part of the technical story:

> "The initial model showed excellent discrimination on a rare-event problem, but LogLoss revealed that its raw probabilities were not sufficiently calibrated for the way the agent intended to communicate risk. I treated ranking and calibration as separate requirements rather than presenting a high AUC as proof that the probabilities were trustworthy."
