from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import run_phase1_pipeline
from retrieval.index import LocalEmbeddingIndex


def run_corruption_flow(settings: Settings) -> dict[str, Any]:
    """Evaluate corruption, then repair deterministically from the raw anchor."""
    if not settings.paths.baseline_metrics.exists() or not settings.paths.clean_json.exists():
        run_phase1_pipeline(settings)

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_quality = read_json(settings.paths.baseline_quality_report)
    baseline_freshness = read_json(settings.paths.quality_dir / "baseline_freshness_report.json")
    clean_df = pd.read_json(settings.paths.clean_json)

    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, settings.paths.corrupted_embeddings_json
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")

    # Repair is idempotent: reconstruct from immutable raw records, never by
    # trying to infer lost values from the corrupted dataframe.
    repaired_df = build_clean_dataframe(
        load_raw_records(settings.paths.raw_records_json), datetime.now(UTC)
    )
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, settings.paths.repaired_embeddings_json
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")

    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_evaluation.summary,
        repaired_metrics=repaired_evaluation.summary,
        baseline_quality=baseline_quality,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        baseline_freshness=baseline_freshness,
        corrupted_freshness=corrupted_quality["freshness"],
        repaired_freshness=repaired_quality["freshness"],
    )
    return {
        "baseline": baseline_metrics,
        "corrupted": corrupted_evaluation.summary,
        "repaired": repaired_evaluation.summary,
        "report_path": str(settings.paths.comparison_report),
    }


def main() -> None:
    """CLI entry point used by ``python script/run_corruption_flow.py``."""
    result = run_corruption_flow(load_settings())
    print("| Metric | Baseline | Corrupted | Repaired |")
    print("| --- | ---: | ---: | ---: |")
    for metric in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        print(
            f"| {metric} | {result['baseline'][metric]:.3f} | "
            f"{result['corrupted'][metric]:.3f} | {result['repaired'][metric]:.3f} |"
        )
    print(f"Report: {result['report_path']}")
