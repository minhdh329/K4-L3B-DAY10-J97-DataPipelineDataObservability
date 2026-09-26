from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_csv
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Run corrupted, repaired, and comparison phases from the baseline artifacts."""
    clean_dataframe = pd.read_json(settings.paths.clean_json)
    baseline_metrics = read_json(settings.paths.baseline_metrics)

    corrupted_dataframe = corrupt_clean_dataframe(
        clean_dataframe, settings.paths.corruption_log
    )
    _save_dataframe(
        corrupted_dataframe,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_dataframe,
        settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(
        corrupted_dataframe, settings, "corrupted_quality_report"
    )
    corrupted_freshness = build_freshness_report(
        corrupted_dataframe,
        settings,
        settings.paths.quality_dir / "corrupted_freshness_report.json",
    )

    repaired_records = load_raw_records(settings.paths.raw_records_json)
    repaired_dataframe = build_clean_dataframe(
        repaired_records, datetime.now(timezone.utc)
    )
    _save_dataframe(
        repaired_dataframe,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    repaired_index = LocalEmbeddingIndex.build(
        repaired_dataframe,
        settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_bundle = evaluate_pipeline(
        settings,
        repaired_index,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(
        repaired_dataframe, settings, "repaired_quality_report"
    )
    repaired_freshness = build_freshness_report(
        repaired_dataframe,
        settings,
        settings.paths.quality_dir / "repaired_freshness_report.json",
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_bundle.summary,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    return {
        "baseline": baseline_metrics,
        "corrupted": corrupted_bundle.summary,
        "repaired": repaired_bundle.summary,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "corrupted_freshness": corrupted_freshness,
        "repaired_freshness": repaired_freshness,
    }


def _save_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(json_path, orient="records", force_ascii=False, indent=2, date_format="iso")


def main() -> None:
    result = run_corruption_flow_pipeline(load_settings())
    print("Corruption flow complete")
    print(
        "Baseline vs Corrupted vs Repaired: "
        f"{result['baseline'].get('retrieval_hit_rate', 0):.3f} / "
        f"{result['corrupted'].get('retrieval_hit_rate', 0):.3f} / "
        f"{result['repaired'].get('retrieval_hit_rate', 0):.3f}"
    )
