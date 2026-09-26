from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.config import Settings, load_settings
from core.utils import write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Run the reproducible clean-data baseline from ingestion through report."""
    records = fetch_source_records(settings)
    clean_df = build_clean_dataframe(records, datetime.now(UTC))
    if clean_df.empty:
        raise RuntimeError("Cleaning produced no records; baseline index cannot be built.")
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(clean_df, settings)
    test_set = build_test_set(clean_df, settings.paths.eval_testset)
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    source_summary = {
        "source": settings.source_api,
        "query": settings.source_query,
        "records_fetched": len(records),
        "records_clean": len(clean_df),
        "embedding_model": settings.embedding_model,
        "collection_name": index.collection_name,
        "test_set_size": len(test_set),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=quality["freshness"],
    )
    return {
        "source": source_summary,
        "metrics": evaluation.summary,
        "quality": quality,
        "report_path": str(settings.paths.baseline_report),
    }


def main() -> None:
    """CLI entry point used by ``python script/run_phase1.py``."""
    result = run_phase1_pipeline(load_settings())
    metrics = result["metrics"]
    print(
        "Phase 1 complete: "
        f"hit_rate={metrics['retrieval_hit_rate']:.3f}, "
        f"token_f1={metrics['mean_token_f1']:.3f}"
    )
    print(f"Report: {result['report_path']}")
