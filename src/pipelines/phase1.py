from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
import logging
from typing import Any

import requests

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


logger = logging.getLogger(__name__)


def _ingest(settings: Settings):
    paths = settings.paths
    cached = paths.raw_records_json.exists() or paths.raw_api_response.exists()
    if settings.refresh_source or not cached:
        try:
            return fetch_source_records(settings), "crossref_api"
        except requests.RequestException:
            if not cached:
                raise
            logger.warning("Crossref request failed; using the existing raw snapshot.")
    if paths.raw_records_json.exists():
        return load_raw_records(paths.raw_records_json), "raw_records_snapshot"
    records = parse_crossref_payload(read_json(paths.raw_api_response))
    write_json(paths.raw_records_json, [asdict(record) for record in records])
    return records, "raw_response_snapshot"


def _valid_cached_testset(test_set: Any, paper_ids: set[str]) -> bool:
    if not isinstance(test_set, list) or len(test_set) != 10:
        return False
    if not all(
        isinstance(item, dict)
        and all(isinstance(item.get(key), str) and item[key].strip()
                for key in ("id", "question_type", "question", "ground_truth"))
        and isinstance(item.get("ground_truth_doc_ids"), list)
        and bool(item["ground_truth_doc_ids"])
        and all(isinstance(doi, str) and doi in paper_ids for doi in item["ground_truth_doc_ids"])
        for item in test_set
    ):
        return False
    return (
        len({item["id"] for item in test_set}) == 10
        and Counter(item["question_type"] for item in test_set)
        == {"summary": 3, "authors": 3, "date": 2, "categories": 2}
    )


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Run the baseline, enforcing GX/freshness before any vector-store write.

    Reuse valid raw/test snapshots unless refresh is requested. A failed gate
    produces a blocked report and raises without building an index or evaluating.
    """
    paths = settings.paths
    run_date = now_utc()
    logger.info("Ingest: loading source records")
    records, source_mode = _ingest(settings)
    logger.info("Clean: normalizing %s raw records", len(records))
    df = build_clean_dataframe(records, run_date)
    write_csv(df, paths.clean_csv)
    write_json(paths.clean_json, df.to_dict(orient="records"))
    source_summary = {
        "source_api": settings.source_api,
        "source_mode": source_mode,
        "run_date": run_date.isoformat(),
        "raw_records": len(records),
        "clean_records": len(df),
        "embedding_model": settings.embedding_model,
        "collection_name": settings.baseline_collection_name,
        "top_k": settings.top_k,
    }

    logger.info("Quality gate: validating GX expectations and freshness")
    quality = run_data_quality_checks(df, settings, stage="baseline")
    freshness = build_freshness_report(df, settings, paths.freshness_report)
    if not quality["success"]:
        generate_phase1_report(paths.baseline_report, source_summary, {}, quality, freshness)
        raise RuntimeError(f"Quality gate failed; indexing blocked. See {paths.baseline_report}")

    logger.info("Index: embedding %s documents into ChromaDB", len(df))
    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=paths.embeddings_json)

    logger.info("Test set: loading or generating 10 ground-truth questions")
    test_set = None
    regenerate = settings.refresh_test_set or source_mode == "crossref_api"
    if not regenerate and paths.eval_testset.exists():
        try:
            test_set = read_json(paths.eval_testset)
        except (json.JSONDecodeError, UnicodeError):
            logger.warning("Test-set snapshot is not valid JSON; regenerating it.")
    regenerate = regenerate or not _valid_cached_testset(test_set, set(df["paper_id"]))
    if regenerate:
        test_set = build_test_set(df, paths.eval_testset)
    source_summary["testset_mode"] = "generated" if regenerate else "snapshot"
    source_summary["testset_questions"] = len(test_set)

    logger.info("Evaluate: computing baseline retrieval hit rate and token F1")
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.baseline_metrics,
        answers_output_path=paths.baseline_answers,
    )
    logger.info("Report: writing %s", paths.baseline_report)
    generate_phase1_report(paths.baseline_report, source_summary, evaluation.summary, quality, freshness)
    return {
        "success": True,
        "source_summary": source_summary,
        "metrics": evaluation.summary,
        "quality": quality,
        "freshness": freshness,
        "report_path": str(paths.baseline_report),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_phase1_pipeline(load_settings())
    metrics = result["metrics"]
    print(f"Baseline completed: {metrics['samples']} questions, "
          f"Hit Rate={metrics['retrieval_hit_rate']:.2%}, Token F1={metrics['mean_token_f1']:.4f}")
    print(f"Report: {result['report_path']}")
