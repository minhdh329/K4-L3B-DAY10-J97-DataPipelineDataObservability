from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """TODO(student): tao bo data quality checks.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"{report_name}_source")
    data_asset = data_source.add_dataframe_asset(name=f"{report_name}_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe(
        f"{report_name}_batch"
    )
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
    validator = context.get_validator(batch=batch)

    checks = [
        (
            "row_count",
            validator.expect_table_row_count_to_be_between(
                min_value=5, max_value=5000
            ),
        ),
        (
            "paper_id_not_null",
            validator.expect_column_values_to_not_be_null("paper_id"),
        ),
        (
            "title_not_null",
            validator.expect_column_values_to_not_be_null("title"),
        ),
        (
            "text_for_embedding_not_null",
            validator.expect_column_values_to_not_be_null("text_for_embedding"),
        ),
        (
            "paper_id_unique",
            validator.expect_column_values_to_be_unique("paper_id"),
        ),
        (
            "summary_min_length",
            validator.expect_column_value_lengths_to_be_between(
                "summary", min_value=30
            ),
        ),
    ]
    expectation_results = [
        {"name": name, "success": result.success, "result": result.to_json_dict().get("result", {})}
        for name, result in checks
    ]
    freshness = evaluate_freshness_sla(df, settings)
    report = {
        "success": all(item["success"] for item in expectation_results)
        and freshness["is_fresh"],
        "report_name": report_name,
        "expectations": expectation_results,
        "freshness": freshness,
    }
    report_path = settings.paths.quality_dir / f"{report_name}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """TODO(student): tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    report = evaluate_freshness_sla(df, settings)
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    total_rows = len(df)
    stale_rows = int((pd.to_numeric(df.get("age_days"), errors="coerce") > settings.freshness_threshold_days).sum()) if total_rows else 0
    published = pd.to_datetime(df.get("published"), errors="coerce") if total_rows else pd.Series(dtype="datetime64[ns]")
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    return {
        "latest_published": published.max().date().isoformat() if published.notna().any() else None,
        "oldest_published": published.min().date().isoformat() if published.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": settings.freshness_threshold_days,
        "is_fresh": stale_ratio <= 0.25,
    }
