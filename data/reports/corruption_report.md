# Corruption Comparison Report

| Phase | Retrieval hit rate | Mean token F1 | Quality | Freshness |
|---|---:|---:|---|---|
| Baseline | 1.000 | 0.207 |  |  |
| Corrupted | 0.500 | 0.141 | False | True |
| Repaired | 1.000 | 0.207 | True | True |

## Raw payload

```json
{
  "baseline": {
    "samples": 10,
    "retrieval_hit_rate": 1.0,
    "mean_token_f1": 0.20731475546797024,
    "judge_accuracy": 0.2,
    "mean_judge_score": 1.4,
    "ragas": {
      "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
    }
  },
  "corrupted": {
    "samples": 10,
    "retrieval_hit_rate": 0.5,
    "mean_token_f1": 0.14069529652351737,
    "judge_accuracy": 0.2,
    "mean_judge_score": 1.4,
    "ragas": {
      "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
    }
  },
  "repaired": {
    "samples": 10,
    "retrieval_hit_rate": 1.0,
    "mean_token_f1": 0.20731475546797024,
    "judge_accuracy": 0.2,
    "mean_judge_score": 1.4,
    "ragas": {
      "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
    }
  },
  "corrupted_quality": {
    "success": false,
    "report_name": "corrupted_quality_report",
    "expectations": [
      {
        "name": "row_count",
        "success": true,
        "result": {
          "observed_value": 21
        }
      },
      {
        "name": "paper_id_not_null",
        "success": true,
        "result": {
          "element_count": 21,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": []
        }
      },
      {
        "name": "title_not_null",
        "success": true,
        "result": {
          "element_count": 21,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": []
        }
      },
      {
        "name": "text_for_embedding_not_null",
        "success": true,
        "result": {
          "element_count": 21,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": []
        }
      },
      {
        "name": "paper_id_unique",
        "success": false,
        "result": {
          "element_count": 21,
          "unexpected_count": 4,
          "unexpected_percent": 19.047619047619047,
          "partial_unexpected_list": [
            "10.28932/jutisi.v12i2.13099",
            "10.20944/preprints202608.1849.v1",
            "10.28932/jutisi.v12i2.13099",
            "10.20944/preprints202608.1849.v1"
          ],
          "missing_count": 0,
          "missing_percent": 0.0,
          "unexpected_percent_total": 19.047619047619047,
          "unexpected_percent_nonmissing": 19.047619047619047
        }
      },
      {
        "name": "summary_min_length",
        "success": false,
        "result": {
          "element_count": 21,
          "unexpected_count": 4,
          "unexpected_percent": 19.047619047619047,
          "partial_unexpected_list": [
            "",
            "",
            "",
            ""
          ],
          "missing_count": 0,
          "missing_percent": 0.0,
          "unexpected_percent_total": 19.047619047619047,
          "unexpected_percent_nonmissing": 19.047619047619047
        }
      }
    ],
    "freshness": {
      "latest_published": "2026-08-27",
      "oldest_published": "2025-07-10",
      "stale_rows": 2,
      "total_rows": 21,
      "stale_ratio": 0.09523809523809523,
      "threshold_days": 180,
      "is_fresh": true
    }
  },
  "repaired_quality": {
    "success": true,
    "report_name": "repaired_quality_report",
    "expectations": [
      {
        "name": "row_count",
        "success": true,
        "result": {
          "observed_value": 24
        }
      },
      {
        "name": "paper_id_not_null",
        "success": true,
        "result": {
          "element_count": 24,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": []
        }
      },
      {
        "name": "title_not_null",
        "success": true,
        "result": {
          "element_count": 24,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": []
        }
      },
      {
        "name": "text_for_embedding_not_null",
        "success": true,
        "result": {
          "element_count": 24,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": []
        }
      },
      {
        "name": "paper_id_unique",
        "success": true,
        "result": {
          "element_count": 24,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": [],
          "missing_count": 0,
          "missing_percent": 0.0,
          "unexpected_percent_total": 0.0,
          "unexpected_percent_nonmissing": 0.0
        }
      },
      {
        "name": "summary_min_length",
        "success": true,
        "result": {
          "element_count": 24,
          "unexpected_count": 0,
          "unexpected_percent": 0.0,
          "partial_unexpected_list": [],
          "missing_count": 0,
          "missing_percent": 0.0,
          "unexpected_percent_total": 0.0,
          "unexpected_percent_nonmissing": 0.0
        }
      }
    ],
    "freshness": {
      "latest_published": "2026-09-15",
      "oldest_published": "2026-04-01",
      "stale_rows": 0,
      "total_rows": 24,
      "stale_ratio": 0.0,
      "threshold_days": 180,
      "is_fresh": true
    }
  },
  "corrupted_freshness": {
    "latest_published": "2026-08-27",
    "oldest_published": "2025-07-10",
    "stale_rows": 2,
    "total_rows": 21,
    "stale_ratio": 0.09523809523809523,
    "threshold_days": 180,
    "is_fresh": true
  },
  "repaired_freshness": {
    "latest_published": "2026-09-15",
    "oldest_published": "2026-04-01",
    "stale_rows": 0,
    "total_rows": 24,
    "stale_ratio": 0.0,
    "threshold_days": 180,
    "is_fresh": true
  }
}
```
