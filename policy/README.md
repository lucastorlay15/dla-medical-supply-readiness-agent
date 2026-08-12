# Synthetic Policy Corpus

This directory contains the demo-only policy corpus for **Tool 2 — Policy / Contract RAG** in the DLA Medical Supply Readiness Agent.

> **Important:** Every policy in this directory is synthetic and exists only for the interview prototype. These files are not official DLA, DoD, or DHA policy.

## Files

- `POL-001-medical-stocking-and-readiness.md` — stocking thresholds aligned to the synthetic item-generation logic and existing `policy_reference_id` values.
- `POL-002-shortage-escalation-and-emergency-sourcing.md` — shortage escalation, mitigation sequence, predictive-risk trigger, and human-approval guidance.
- `POL-003-supplier-performance-escalation.md` — supplier-performance and disruption escalation guidance.
- `POL-004-cold-chain-readiness.md` — cold-chain readiness and contingency guidance.
- `policy_sections.csv` — RAG-ready representation of the policy corpus for DataRobot ingestion.

## RAG ingestion design

`policy_sections.csv` is intentionally pre-chunked. **One CSV row represents one complete policy section / retrieval unit.**

Required retrieval text and source fields:

- `document` — the complete text to embed and retrieve.
- `document_file_path` — the human-readable source policy file associated with that row.

Additional metadata:

- `policy_reference_id`
- `policy_title`
- `section_id`
- `policy_type`
- `authority`
- `effective_date`
- `synthetic_policy`
- `applies_to`

For the MVP, ingest `policy_sections.csv` into a DataRobot-managed vector database using **no additional chunking**, because the rows are already curated as semantic units.

## Relationship to operational data

The synthetic `dim_medical_item.policy_reference_id` values are generated as `MED-STOCK-<FSC>`. The stocking rows in `policy_sections.csv` use those same IDs so the agent can connect an operational item to the appropriate policy guidance without embedding operational database rows.

Operational facts remain in Databricks and are queried through Tool 1 / Genie. Only semantic policy knowledge is embedded for Tool 2.

## Intended Tool 2 behavior

Tool 2 should answer questions such as:

- What minimum stocking rule applies to this item?
- When should a near-threshold position be escalated?
- When should emergency sourcing be considered?
- What supplier-performance threshold requires review?
- What special guidance applies to cold-chain items?

Policy answers should preserve source metadata and should not substitute for operational facts from Tool 1 or shortage probabilities from Tool 3.
