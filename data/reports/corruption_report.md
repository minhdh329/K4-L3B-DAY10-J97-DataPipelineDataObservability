# Corruption and repair — comparison report

All states use the same raw snapshot, run date, embedding model and Ground Truth.
The baseline was measured again for this experiment; old metric files were not reused.

## Three-state comparison

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Rows | 24 | 21 | 24 |
| Questions | 10 | 10 | 10 |
| Retrieval Hit Rate | 100.00% | 90.00% | 100.00% |
| Mean Token F1 | 0.8000 | 0.7192 | 0.8000 |
| Quality gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | FAIL | PASS |
| Stale ratio | 0.00% | 28.57% | 0.00% |

## Measured degradation and recovery

- Hit Rate: corrupted minus baseline = -0.1000; repaired minus corrupted = +0.1000; repaired minus baseline = +0.0000.
- Token F1: corrupted minus baseline = -0.0808; repaired minus corrupted = +0.0808; repaired minus baseline = +0.0000.

## Silent Failure

Corrupted indexing and evaluation completed without a runtime error. Answer/retrieval metrics declined.
The experiment deliberately bypassed the failed quality gate for corrupted data; the normal baseline and repair paths still enforce it.
See the corruption log and failed GX expectations for data faults even when a retrieval metric stays high.

## Safe repair

Repair reads only the original raw snapshot, recomputes clean rows and freshness, and requires a passing quality gate.
Chroma replacement builds a full staging collection before switching names, with rollback on rename failure.
The working clean CSV/JSON and baseline Chroma collection are restored. Corrupted and repaired collections/artifacts remain separate comparison evidence.
Rebuilding replaces old record IDs instead of appending, removing duplicate and obsolete vectors. This is a single-process workflow, not a transaction spanning all JSON/CSV files and Chroma.

## Interpretation

Retrieval combines Chroma vector search and exact-title lookup. Answers are extracted from metadata; these results do not measure a generative LLM alone.
Two category questions may remain incorrect after repair because source metadata lacks categories.

## Artifacts

- [Corruption log](../results/corruption_log.json)
- [Baseline metrics](../results/baseline_metrics.json) / [answers](../results/baseline_answers.json)
- [Corrupted metrics](../results/corrupted_metrics.json) / [answers](../results/corrupted_answers.json)
- [Repaired metrics](../results/repaired_metrics.json) / [answers](../results/repaired_answers.json)
- [Corrupted data](../clean/papers_clean_corrupted.json) / [repaired data](../clean/papers_clean_repaired.json)
- [Corrupted GX](../quality/corrupted_quality_report.json) / [repaired GX](../quality/repaired_quality_report.json)
- [Corrupted freshness](../quality/corrupted_freshness_report.json) / [repaired freshness](../quality/repaired_freshness_report.json)
