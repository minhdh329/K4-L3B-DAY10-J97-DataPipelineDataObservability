from __future__ import annotations

import logging
from pathlib import Path

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question

logger = logging.getLogger(__name__)


def main() -> None:
    """Xay dung baseline pipeline end-to-end.

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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # 1. Load settings
    logger.info("Step 1: Loading settings...")
    settings = load_settings()

    # 2. Load hoac fetch raw records
    logger.info("Step 2: Ingesting raw records...")
    raw_records = fetch_source_records(settings)
    logger.info("Ingested %d raw records.", len(raw_records))

    # 3. Clean data
    logger.info("Step 3: Cleaning raw data...")
    run_date = now_utc()
    df_clean = build_clean_dataframe(raw_records, run_date)
    logger.info("Cleaned %d records.", len(df_clean))

    # 4. Save clean CSV/JSON
    logger.info("Step 4: Saving clean artifacts...")
    write_csv(df_clean, settings.paths.clean_csv)
    df_clean.to_json(settings.paths.clean_json, orient="records", indent=2, date_format="iso")
    logger.info("Saved clean data to %s and %s", settings.paths.clean_csv, settings.paths.clean_json)

    # 5. Build Chroma index
    logger.info("Step 5: Building Chroma vector index (%s)...", settings.baseline_collection_name)
    index = LocalEmbeddingIndex.build(
        df=df_clean,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    logger.info(
        "Indexed %d documents into ChromaDB collection '%s'.",
        index.collection.count(),
        settings.baseline_collection_name,
    )

    # 6. Tao hoac load evaluation set
    logger.info("Step 6: Building/loading evaluation test set...")
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(df_clean, settings.paths.eval_testset)
        logger.info("Generated new evaluation test set with %d questions.", len(test_set))
    else:
        test_set = read_json(settings.paths.eval_testset)
        logger.info("Loaded existing evaluation test set with %d questions.", len(test_set))

    # 7. Evaluate
    logger.info("Step 7: Evaluating baseline pipeline...")
    evaluation_bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    metrics = evaluation_bundle.summary
    logger.info(
        "Evaluation summary: Hit Rate=%.4f, Token F1=%.4f, Judge Acc=%.4f",
        metrics.get("retrieval_hit_rate", 0.0),
        metrics.get("mean_token_f1", 0.0),
        metrics.get("judge_accuracy", 0.0),
    )

    # 8. Run quality checks va freshness report
    logger.info("Step 8: Running data quality checks and freshness monitoring...")
    quality = run_data_quality_checks(df_clean, settings, report_name="baseline")
    freshness = build_freshness_report(df_clean, settings, settings.paths.freshness_report)
    logger.info(
        "Quality check success: %s, Freshness status: %s",
        quality.get("success"),
        freshness.get("is_fresh"),
    )

    # 9. Tao markdown report
    logger.info("Step 9: Generating Phase 1 markdown report...")
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_records_count": len(raw_records),
        "clean_records_count": len(df_clean),
        "embedding_model": settings.embedding_model,
        "collection_name": settings.baseline_collection_name,
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=metrics,
        quality=quality,
        freshness=freshness,
    )
    logger.info("Saved Phase 1 report to %s", settings.paths.baseline_report)

    # 10. Co the demo agent tren vai sample question
    logger.info("Step 10: Running sample QA demonstration...")
    demo_samples = []
    for item in test_set[:3]:
        q = item["question"]
        try:
            agent = build_agent(settings, index)
            ans = run_agent_question(agent, q)
        except Exception as exc:
            logger.info("Agent fallback to direct QA extractor (%s)", exc)
            ans_res = answer_question(q, settings, index)
            ans = ans_res.answer
        demo_samples.append(
            {
                "question": q,
                "answer": ans,
                "ground_truth": item["ground_truth"],
            }
        )
    write_json(settings.paths.demo_answers, demo_samples)
    logger.info("Phase 1 baseline pipeline completed successfully!")
