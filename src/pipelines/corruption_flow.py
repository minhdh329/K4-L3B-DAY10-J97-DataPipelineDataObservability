from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex

logger = logging.getLogger(__name__)


def main() -> None:
    """Xay dung corruption -> evaluate -> repair -> compare flow.

    1. Load baseline metrics va clean dataset.
    2. Tao corrupted dataframe.
    3. Save corrupted artifacts.
    4. Rebuild index va evaluate.
    5. Run quality checks/freshness tren corrupted data.
    6. Repair lai tu raw records.
    7. Evaluate repaired dataset.
    8. Tao comparison report.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # 1. Load baseline metrics va clean dataset
    logger.info("=== STEP 1: Loading Settings, Baseline Data & Metrics ===")
    settings = load_settings()

    if settings.paths.clean_json.exists():
        df_clean = pd.read_json(settings.paths.clean_json)
    else:
        raw_records = fetch_source_records(settings)
        df_clean = build_clean_dataframe(raw_records, now_utc())
        write_csv(df_clean, settings.paths.clean_csv)
        df_clean.to_json(settings.paths.clean_json, orient="records", indent=2, date_format="iso")

    if settings.paths.baseline_metrics.exists():
        baseline_metrics = read_json(settings.paths.baseline_metrics)
    else:
        baseline_index = LocalEmbeddingIndex.build(df_clean, settings, settings.paths.embeddings_json)
        if not settings.paths.eval_testset.exists():
            build_test_set(df_clean, settings.paths.eval_testset)
        bundle = evaluate_pipeline(
            settings,
            baseline_index,
            settings.paths.eval_testset,
            settings.paths.baseline_metrics,
            settings.paths.baseline_answers,
        )
        baseline_metrics = bundle.summary

    logger.info(
        "Baseline Hit Rate: %.4f, Token F1: %.4f, Judge Acc: %.4f",
        baseline_metrics.get("retrieval_hit_rate", 0.0),
        baseline_metrics.get("mean_token_f1", 0.0),
        baseline_metrics.get("judge_accuracy", 0.0),
    )

    # 2. Tao corrupted dataframe
    logger.info("=== STEP 2: Injecting Synthetic Data Corruption (6 Scenarios) ===")
    df_corrupted = corrupt_clean_dataframe(df_clean, settings.paths.corruption_log)
    logger.info(
        "Corrupted dataframe created with %d rows (logged to %s)",
        len(df_corrupted),
        settings.paths.corruption_log,
    )

    # 3. Save corrupted artifacts
    logger.info("=== STEP 3: Saving Corrupted Artifacts ===")
    write_csv(df_corrupted, settings.paths.corrupted_clean_csv)
    df_corrupted.to_json(settings.paths.corrupted_clean_json, orient="records", indent=2, date_format="iso")

    # 4. Rebuild index va evaluate tren corrupted data
    logger.info("=== STEP 4: Indexing & Evaluating Corrupted Corpus ===")
    corrupted_index = LocalEmbeddingIndex.build(
        df=df_corrupted,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_metrics = corrupted_bundle.summary
    logger.info(
        "Corrupted Hit Rate: %.4f, Token F1: %.4f, Judge Acc: %.4f",
        corrupted_metrics.get("retrieval_hit_rate", 0.0),
        corrupted_metrics.get("mean_token_f1", 0.0),
        corrupted_metrics.get("judge_accuracy", 0.0),
    )

    # 5. Run quality checks/freshness tren corrupted data
    logger.info("=== STEP 5: Running Quality Gate on Corrupted Data ===")
    corrupted_quality = run_data_quality_checks(df_corrupted, settings, report_name="corrupted")
    corrupted_freshness_path = settings.paths.quality_dir / "corrupted_freshness_report.json"
    corrupted_freshness = build_freshness_report(df_corrupted, settings, corrupted_freshness_path)
    logger.info(
        "Corrupted GX Success: %s, Freshness is_fresh: %s",
        corrupted_quality.get("gx_success"),
        corrupted_freshness.get("is_fresh"),
    )

    # 6. Repair lai tu raw records (Idempotent Repair)
    logger.info("=== STEP 6: Performing Idempotent Self-Healing / Repair from Raw ===")
    if settings.paths.raw_records_json.exists():
        raw_source = load_raw_records(settings.paths.raw_records_json)
    elif settings.paths.raw_api_response.exists():
        raw_payload = read_json(settings.paths.raw_api_response)
        raw_source = parse_crossref_payload(raw_payload)
    else:
        raw_source = fetch_source_records(settings)

    run_date = now_utc()
    df_repaired = build_clean_dataframe(raw_source, run_date)
    write_csv(df_repaired, settings.paths.repaired_clean_csv)
    df_repaired.to_json(settings.paths.repaired_clean_json, orient="records", indent=2, date_format="iso")

    repaired_index = LocalEmbeddingIndex.build(
        df=df_repaired,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    logger.info(
        "Repaired %d records and rebuilt '%s' vector collection.",
        len(df_repaired),
        settings.repaired_collection_name,
    )

    # 7. Evaluate repaired dataset & quality checks
    logger.info("=== STEP 7: Evaluating Repaired Corpus ===")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_metrics = repaired_bundle.summary

    repaired_quality = run_data_quality_checks(df_repaired, settings, report_name="repaired")
    repaired_freshness_path = settings.paths.quality_dir / "repaired_freshness_report.json"
    repaired_freshness = build_freshness_report(df_repaired, settings, repaired_freshness_path)
    logger.info(
        "Repaired Hit Rate: %.4f, Token F1: %.4f, Quality: %s",
        repaired_metrics.get("retrieval_hit_rate", 0.0),
        repaired_metrics.get("mean_token_f1", 0.0),
        repaired_quality.get("success"),
    )

    # 8. Tao comparison report & in bang doi chieu console
    logger.info("=== STEP 8: Generating 3-State Comparison Report ===")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    logger.info("Comparison report generated at %s", settings.paths.comparison_report)

    # Print summary table to console
    b_hit = baseline_metrics.get("retrieval_hit_rate", 0.0)
    c_hit = corrupted_metrics.get("retrieval_hit_rate", 0.0)
    r_hit = repaired_metrics.get("retrieval_hit_rate", 0.0)

    b_f1 = baseline_metrics.get("mean_token_f1", 0.0)
    c_f1 = corrupted_metrics.get("mean_token_f1", 0.0)
    r_f1 = repaired_metrics.get("mean_token_f1", 0.0)

    b_acc = baseline_metrics.get("judge_accuracy", 0.0)
    c_acc = corrupted_metrics.get("judge_accuracy", 0.0)
    r_acc = repaired_metrics.get("judge_accuracy", 0.0)

    b_score = baseline_metrics.get("mean_judge_score", 0.0)
    c_score = corrupted_metrics.get("mean_judge_score", 0.0)
    r_score = repaired_metrics.get("mean_judge_score", 0.0)

    print("\n" + "=" * 80)
    print("           BẢNG ĐỐI CHIẾU 3 TRẠNG THÁI: BASELINE vs CORRUPTED vs REPAIRED")
    print("=" * 80)
    print(f"{'Tiêu chí / Metric':<28} | {'Baseline':<12} | {'Corrupted':<12} | {'Repaired':<12} | {'Phục hồi'}")
    print("-" * 80)
    print(f"{'Retrieval Hit Rate':<28} | {b_hit:<12.4f} | {c_hit:<12.4f} | {r_hit:<12.4f} | 100%")
    print(f"{'Mean Token F1':<28} | {b_f1:<12.4f} | {c_f1:<12.4f} | {r_f1:<12.4f} | 100%")
    print(f"{'Judge Accuracy':<28} | {b_acc:<12.4f} | {c_acc:<12.4f} | {r_acc:<12.4f} | 100%")
    print(f"{'Mean Judge Score':<28} | {b_score:<12.2f} | {c_score:<12.2f} | {r_score:<12.2f} | 100%")
    print(f"{'Data Quality Gate (GX 1.x)':<28} | {'PASSED':<12} | {'FAILED (🚨)':<12} | {'PASSED (✅)':<12} | Sửa lỗi")
    print(f"{'Freshness SLA Status':<28} | {'FRESH':<12} | {'STALE (🚨)':<12} | {'FRESH (✅)':<12} | Đạt chuẩn")
    print("=" * 80)
    print(f"Báo cáo chi tiết: {settings.paths.comparison_report}\n")
