# Data Corruption and Repair Report

The same benchmark test set is used for every state. Repair rebuilds from the immutable raw Crossref records, rather than modifying corrupted values in place.

## Performance comparison

| Metric | Baseline | Corrupted | Repaired | Change after corruption | Recovery from corrupted |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.6000 | 1.0000 | -0.4000 | 0.4000 |
| `mean_token_f1` | 1.0000 | 0.7741 | 1.0000 | -0.2259 | 0.2259 |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 | -0.2000 | 0.2000 |
| `mean_judge_score` | 5.0000 | 4.0000 | 5.0000 | -1.0000 | 1.0000 |

## Data observability signals

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Quality gate | PASS | FAIL | PASS |
| Freshness | Fresh (4.17%) | Stale (33.33%) | Fresh (4.17%) |

## Interpretation

- Corruption alters coverage, content, dates, titles, and document identity; quality and freshness signals identify the invalid state before serving.
- The repair run reconstructs clean data and its vector index from the raw lineage anchor, restoring both data signals and evaluation metrics.
