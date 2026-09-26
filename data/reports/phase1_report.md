# Phase 1 — Baseline RAG report

Status: **COMPLETED**

## Source and run

| Field | Value |
| --- | --- |
| source_api | Crossref REST API |
| source_mode | raw_snapshot |
| run_date | 2026-09-26T03:47:19.511077+00:00 |
| raw_records | 24 |
| clean_records | 24 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| collection_name | papers-baseline |
| top_k | 4 |

## Baseline metrics

| Metric | Value |
| --- | ---: |
| Questions | 10 |
| Retrieval Hit Rate | 100.00% |
| Mean Token F1 | 0.8000 |

Hit Rate is the proportion of questions whose expected DOI occurs in retrieved results.
Token F1 uses case-insensitive whitespace tokens and counts repeated tokens.
Answers use metadata extraction. Retrieval combines Chroma vector search with exact-title lookup;
this score is not a vector-search-only benchmark or a generative LLM benchmark.
Missing categories can reduce F1 when the reference expects an explicit absence answer.

LLM judge enabled: False.
Ragas: {'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}

## Great Expectations quality gate

- Overall gate: **PASS**
- GX expectations: 7/7 passed
- Missing required columns: []
- Gate runs before creating or replacing the Chroma collection.

## Freshness SLA

- Fresh: **True**
- Stale rows: 0/24 (0.00%)
- Stale threshold: age_days > 180
- Maximum stale ratio: 25%
- Invalid ages: 0
- Publication range: 2026-04-01 to 2026-09-15

## Artifacts

- [Raw API response](../raw/crossref_response.json)
- [Raw records](../raw/crossref_records.json)
- [Clean CSV](../clean/papers_clean.csv) / [Clean JSON](../clean/papers_clean.json)
- [GX quality report](../quality/baseline_quality_report.json)
- [Freshness report](../quality/freshness_report.json)
- [Chroma database](../chroma/) / [Embedding manifest](../embeddings/papers_embeddings.json)
- [Ground truth](../eval/test_set.json)
- [Baseline metrics](../results/baseline_metrics.json)
- [Per-question answers](../results/baseline_answers.json)
