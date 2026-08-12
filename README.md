# DLA Medical Supply Readiness Agent

Synthetic, interview-focused prototype for a Defense Logistics Agency (DLA) medical supply readiness agent.

The core question is:

> Which critical medical supplies are at risk of shortage over the next 30 days, where will those shortages occur, why, and what should we do about them?

This repository contains Databricks code for generating governed synthetic Delta tables, a DataRobot agent application, and a small synthetic policy corpus for RAG.

## Repository areas

- `databricks/` — synthetic operational data, analytics products, ML training/scoring datasets, and public reference metrics.
- `datarobot-agent-application/` — DataRobot Agentic Starter workflow and deployment assets for the readiness agent.
- `policy/` — synthetic policy documents plus `policy_sections.csv`, a pre-chunked DataRobot RAG ingestion dataset.
- `PROJECT_PLAN.md` — architecture, tool boundaries, implementation phases, demo flow, and production-readiness plan.

The three MVP capabilities are intentionally specialized:

1. **Tool 1 — Databricks Genie:** observed operational facts, queries, aggregations, trends, and root-cause analysis.
2. **Tool 2 — DataRobot RAG:** policy, stocking rules, sourcing guidance, escalation guidance, and source attribution.
3. **Tool 3 — DataRobot predictive model lookup:** authoritative 30-day shortage probabilities.

> **Important:** All operational records and all policy documents in this project are synthetic. Public DLA metrics are stored separately as reference context and are never presented as generated operational records. The synthetic policy files are not official DLA, DoD, or DHA policy.
