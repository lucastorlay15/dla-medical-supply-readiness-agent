# POL-002 — Synthetic Shortage Escalation and Emergency Sourcing Guidance

> **Demo-only policy.** This document is synthetic and was created for the DLA Medical Supply Readiness Agent interview prototype. It is not an official DLA, DoD, or DHA policy.

## Purpose

Define simple escalation triggers and response guidance when a medical supply position is approaching or has crossed its minimum stocking requirement.

## Escalation triggers

A customer-item position should receive immediate readiness review when current days of supply are below the applicable minimum days of supply.

A position should receive elevated review when it is within five days above the applicable minimum and at least one of the following is true:

- backordered units are greater than zero,
- late inbound units are greater than zero,
- an active supplier disruption affects the preferred supplier.

## Predictive-risk trigger

When the authoritative DataRobot shortage-risk model assigns a 30-day shortage probability of **70% or greater** to a `MISSION_CRITICAL` or `HIGH` item, the planner should prepare a mitigation recommendation even if the position has not yet crossed its minimum stocking threshold.

The predictive probability is a planning signal, not an automatic action. Operational evidence should be reviewed before a recommendation is finalized.

## Preferred mitigation sequence

Planners should consider responses in the following order when feasible:

1. Expedite or validate already-scheduled inbound supply.
2. Review available inventory at lower-risk locations for a potential transfer.
3. Review alternate approved supplier or sourcing options.
4. Prepare an emergency sourcing recommendation when ordinary replenishment cannot restore readiness in time.

## Human approval

The readiness agent may recommend or draft a mitigation action, but it must not execute a transfer, supplier change, purchase action, or emergency sourcing request without authorized human approval.
