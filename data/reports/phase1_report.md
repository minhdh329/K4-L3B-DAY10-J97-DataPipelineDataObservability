# Phase 1 — Baseline Pipeline Report

## Source and index

| Item | Value |
| --- | --- |
| source | Crossref REST API |
| query | agentic retrieval augmented generation large language model |
| records fetched | 24 |
| records clean | 24 |
| embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| collection name | papers-baseline |
| test set size | 10 |

## Baseline evaluation

| Metric | Value |
| --- | ---: |
| `samples` | 10.0000 |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 1.0000 |
| `judge_accuracy` | 1.0000 |
| `mean_judge_score` | 5.0000 |

Ragas: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## Data quality gate

Overall quality gate: **PASS**

| Check | Status | Observed value |
| --- | --- | --- |
| row_count | PASS | 24 |
| paper_id_not_null | PASS | None |
| title_not_null | PASS | None |
| text_for_embedding_not_null | PASS | None |
| paper_id_unique | PASS | None |
| summary_length | PASS | None |

## Freshness SLA

| Item | Value |
| --- | --- |
| Status | Fresh |
| Stale records | 1 / 24 (4.17%) |
| Threshold | age_days > 180 days; maximum stale ratio 25% |
| Latest published | 2026-07-22 |
| Oldest published | 2026-03-28 |
