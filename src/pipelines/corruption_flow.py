from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records, parse_crossref_payload
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report, generate_phase1_report
from pipelines.phase1 import _valid_cached_testset
from retrieval.index import LocalEmbeddingIndex


logger = logging.getLogger(__name__)


@dataclass
class RepairResult:
    dataframe: pd.DataFrame
    index: LocalEmbeddingIndex
    quality: dict[str, Any]
    freshness: dict[str, Any]


def _snapshot_records(settings: Settings):
    """Offline only: never refresh or modify the trusted raw snapshot."""
    if settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)
    if settings.paths.raw_api_response.exists():
        return parse_crossref_payload(read_json(settings.paths.raw_api_response))
    raise FileNotFoundError("Repair requires a local Crossref raw snapshot. Run ingestion first.")


def repair_from_raw_snapshot(settings: Settings, run_date: datetime | None = None) -> RepairResult:
    """Reconstruct from raw, gate, then replace the working corpus and vector index.

    The repaired collection/artifacts are retained separately from corrupted
    evidence. Repeated calls at the same run_date yield the same unique records.
    """
    paths = settings.paths
    repaired = build_clean_dataframe(_snapshot_records(settings), run_date or now_utc())
    quality = run_data_quality_checks(repaired, settings, stage="repaired")
    freshness = build_freshness_report(repaired, settings, paths.quality_dir / "repaired_freshness_report.json")
    if not quality["success"]:
        raise RuntimeError("Raw snapshot failed the repair quality gate; working data/index were not replaced.")
    index = LocalEmbeddingIndex.build(repaired, settings, paths.repaired_embeddings_json)
    # Restore the actual working collection as well as the comparison snapshot.
    LocalEmbeddingIndex.build(repaired, settings, paths.embeddings_json)
    write_csv(repaired, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired.to_dict(orient="records"))
    write_csv(repaired, paths.clean_csv)
    write_json(paths.clean_json, repaired.to_dict(orient="records"))
    return RepairResult(repaired, index, quality, freshness)


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Compare three states with one raw snapshot, run time and frozen test set.

    Only this explicit corruption experiment bypasses the gate for bad data.
    Repair is attempted even if corrupted indexing/evaluation raises an error.
    """
    paths = settings.paths
    if len({settings.baseline_collection_name, settings.corrupted_collection_name,
            settings.repaired_collection_name}) != 3:
        raise ValueError("Baseline, corrupted and repaired collections must have distinct names.")
    run_date = now_utc()
    records = _snapshot_records(settings)
    baseline_df = build_clean_dataframe(records, run_date)
    baseline_quality = run_data_quality_checks(baseline_df, settings, stage="baseline")
    baseline_freshness = build_freshness_report(baseline_df, settings, paths.freshness_report)
    if not baseline_quality["success"]:
        raise RuntimeError("Baseline raw snapshot failed quality checks; corruption was not started.")
    if paths.eval_testset.exists():
        if not _valid_cached_testset(read_json(paths.eval_testset), set(baseline_df["paper_id"])):
            raise ValueError("Existing Ground Truth does not match the raw corpus. Rebuild it before this experiment.")
    else:
        build_test_set(baseline_df, paths.eval_testset)

    logger.info("Baseline: rebuilding and evaluating the trusted corpus")
    write_csv(baseline_df, paths.clean_csv)
    write_json(paths.clean_json, baseline_df.to_dict(orient="records"))
    baseline_index = LocalEmbeddingIndex.build(baseline_df, settings, paths.embeddings_json)
    baseline = evaluate_pipeline(settings, baseline_index, paths.eval_testset,
                                 paths.baseline_metrics, paths.baseline_answers)
    generate_phase1_report(paths.baseline_report, {
        "source_api": settings.source_api, "source_mode": "raw_snapshot",
        "run_date": run_date.isoformat(), "raw_records": len(records),
        "clean_records": len(baseline_df), "embedding_model": settings.embedding_model,
        "collection_name": settings.baseline_collection_name, "top_k": settings.top_k,
    }, baseline.summary, baseline_quality, baseline_freshness)

    logger.info("Corruption: injecting six faults and retaining evidence")
    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, stage="corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json",
    )
    try:
        # Deliberate gate bypass solely to demonstrate Silent Failure.
        logger.warning("Experiment: indexing corrupted data despite quality success=%s", corrupted_quality["success"])
        corrupted_index = LocalEmbeddingIndex.build(corrupted_df, settings, paths.corrupted_embeddings_json)
        LocalEmbeddingIndex.build(corrupted_df, settings, paths.embeddings_json)
        write_csv(corrupted_df, paths.clean_csv)
        write_json(paths.clean_json, corrupted_df.to_dict(orient="records"))
        corrupted = evaluate_pipeline(settings, corrupted_index, paths.eval_testset,
                                      paths.corrupted_metrics, paths.corrupted_answers)
    finally:
        logger.info("Repair: restoring the working data/index from raw snapshot")
        repair = repair_from_raw_snapshot(settings, run_date)

    logger.info("Repaired: evaluating with the unchanged Ground Truth")
    repaired = evaluate_pipeline(settings, repair.index, paths.eval_testset,
                                 paths.repaired_metrics, paths.repaired_answers)
    generate_corruption_report(
        paths.comparison_report, baseline.summary, corrupted.summary, repaired.summary,
        corrupted_quality, repair.quality, corrupted_freshness, repair.freshness,
        baseline_quality=baseline_quality, baseline_freshness=baseline_freshness,
    )
    return {
        "success": True,
        "baseline": baseline.summary, "corrupted": corrupted.summary, "repaired": repaired.summary,
        "corrupted_quality": corrupted_quality, "repaired_quality": repair.quality,
        "report_path": str(paths.comparison_report),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_corruption_flow_pipeline(load_settings())
    for stage in ("baseline", "corrupted", "repaired"):
        metrics = result[stage]
        print(f"{stage}: Hit Rate={metrics['retrieval_hit_rate']:.2%}, Token F1={metrics['mean_token_f1']:.4f}")
    print(f"Report: {result['report_path']}")
