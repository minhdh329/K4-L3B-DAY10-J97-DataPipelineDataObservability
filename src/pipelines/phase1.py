from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from core.config import load_settings
from core.utils import write_csv
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """TODO(student): xay dung baseline pipeline end-to-end.

    Pseudo-code:
    1. Load settings.
    2. Load hoac fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Tao hoac load evaluation set.
    7. Evaluate.
    8. Run quality checks va freshness report.
    9. Tao markdown report.
    10. Co the demo agent tren vai sample question.
    """
    settings = load_settings()
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(settings.paths.raw_records_json)

    dataframe = build_clean_dataframe(records, datetime.now(timezone.utc))
    write_csv(dataframe, settings.paths.clean_csv)
    settings.paths.clean_json.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_json(
        settings.paths.clean_json,
        orient="records",
        force_ascii=False,
        indent=2,
        date_format="iso",
    )

    index = LocalEmbeddingIndex.build(
        dataframe, settings, embeddings_output_path=settings.paths.embeddings_json
    )
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(dataframe, settings.paths.eval_testset)

    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(dataframe, settings, "baseline_quality_report")
    freshness = build_freshness_report(
        dataframe, settings, settings.paths.freshness_report
    )
    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "records": len(records),
        "clean_rows": len(dataframe),
        "collection_name": index.collection_name,
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        freshness,
    )
    print(f"Baseline pipeline complete: {len(dataframe)} clean rows")
