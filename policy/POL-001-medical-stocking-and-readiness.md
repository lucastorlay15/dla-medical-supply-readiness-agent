# POL-001 — Synthetic Medical Stocking and Readiness Policy

> **Demo-only policy.** This document is synthetic and was created for the DLA Medical Supply Readiness Agent interview prototype. It is not an official DLA, DoD, or DHA policy.

## Purpose

Define simple stocking thresholds for the synthetic medical supply dataset so the readiness agent can explain what minimum stock rule applies to an item and how location priority changes that requirement.

## Base minimum days of supply

| Policy reference | Commodity / FSC-style family | Base minimum days of supply |
|---|---|---:|
| `MED-STOCK-6505` | Pharmaceuticals / Preventive Vaccines | 30 |
| `MED-STOCK-6509` | Veterinary Pharmaceuticals | 21 |
| `MED-STOCK-6510` | Surgical Dressing Materials | 21 |
| `MED-STOCK-6515` | Medical/Surgical | 21 |
| `MED-STOCK-6515` | Critical Care | 30 |
| `MED-STOCK-6520` | Dental Items | 14 |
| `MED-STOCK-6525` | Biomedical Equipment | 30 |
| `MED-STOCK-6540` | Optical Items | 14 |
| `MED-STOCK-6545` | Replenishable Field Kits | 30 |
| `MED-STOCK-6550` | Diagnostic Kits/Reagents | 21 |
| `MED-STOCK-6640` | Laboratory Items | 21 |

## Criticality modifier

Apply the following modifier to the base minimum:

- `MISSION_CRITICAL`: add 7 days.
- `HIGH`: add 3 days.
- `ROUTINE`: add 0 days.

## Location mission-priority modifier

For synthetic customer locations with `mission_priority` 4 or 5, add 3 additional days to the minimum stock requirement.

The resulting minimum is:

> **minimum days of supply = base minimum + criticality modifier + mission-priority modifier**

## Readiness interpretation

A position below its calculated minimum days of supply is a current readiness exception and should be reviewed immediately. A position within five days above its minimum is considered a near-threshold watch item, especially when backorders, late inbound supply, or supplier disruption are also present.
