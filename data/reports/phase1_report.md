# Baseline Data Pipeline & Observability Report (Phase 1)

## 1. Source Summary
- **Source API:** Crossref REST API
- **Query:** `agentic retrieval augmented generation large language model`
- **Filter:** `from-pub-date:2026-03-30,has-abstract:true`
- **Raw Records Ingested:** 24
- **Cleaned Records:** 24
- **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Collection:** `papers-baseline`

---

## 2. Baseline Retrieval & Evaluation Metrics
| Metric | Value |
| :--- | :--- |
| **Total Test Samples** | 10 |
| **Retrieval Hit Rate** | 1.0000 (100.0%) |
| **Mean Token F1** | 1.0000 |
| **Judge Accuracy** | 1.0000 (100.0%) |
| **Mean Judge Score** | 5.00 / 5.0 |

---

## 3. Data Quality Gate (Great Expectations 1.x)
- **Overall Quality Status:** **PASSED**
- **Expectation Suite Success:** True
- **Total Expectations Checked:** 6

| Expectation Type | Column | Status |
| :--- | :--- | :--- |
| `expect_table_row_count_to_be_between` | `-` | **PASS** |
| `expect_column_values_to_not_be_null` | `paper_id` | **PASS** |
| `expect_column_values_to_be_unique` | `paper_id` | **PASS** |
| `expect_column_values_to_not_be_null` | `title` | **PASS** |
| `expect_column_values_to_not_be_null` | `text_for_embedding` | **PASS** |
| `expect_column_value_lengths_to_be_between` | `summary` | **PASS** |

---

## 4. Freshness SLA Monitoring
- **Freshness Status:** **FRESH (PASSED SLA)**
- **Total Records:** 24
- **Stale Records (> 180 days):** 1
- **Stale Ratio:** 4.17% (Threshold: <= 25.0%)
- **Latest Published Date:** `2026-07-22`
- **Oldest Published Date:** `2026-03-28`
