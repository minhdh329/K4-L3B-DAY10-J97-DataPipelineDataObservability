from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, stage: str) -> dict[str, Any]:
    """Run the Great Expectations 1.x gate and freshness SLA for ``df``.

    A new ephemeral context is created on every run, so validation has no
    external GX state and works the same on each team member's machine.
    """
    stage_slug = safe_slug(stage)
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        ("row_count", gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)),
        ("paper_id_not_null", gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id")),
        ("title_not_null", gx.expectations.ExpectColumnValuesToNotBeNull(column="title")),
        (
            "text_for_embedding_not_null",
            gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        ),
        ("paper_id_unique", gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id")),
        (
            "summary_length",
            gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
        ),
    ]

    check_results: list[dict[str, Any]] = []
    for name, expectation in expectations:
        validation = batch.validate(expectation)
        payload = validation.to_json_dict()
        check_results.append(
            {
                "name": name,
                "success": bool(validation.success),
                "observed_value": payload.get("result", {}).get("observed_value"),
                "details": payload,
            }
        )

    freshness_path = settings.paths.quality_dir / f"{stage_slug}_freshness_report.json"
    freshness = build_freshness_report(df, settings, freshness_path)
    quality_success = all(result["success"] for result in check_results)
    result = {
        "stage": stage,
        "success": quality_success and freshness["is_fresh"],
        "quality_success": quality_success,
        "freshness": freshness,
        "checks": check_results,
    }
    report_path = settings.paths.quality_dir / f"{stage_slug}_quality_report.json"
    write_json(report_path, result)
    return result


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: Path
) -> dict[str, Any]:
    """Measure and persist freshness, flagging stale data above the 25% SLA."""
    if "age_days" not in df.columns:
        raise ValueError("Freshness check requires an 'age_days' column.")
    if "published" not in df.columns:
        raise ValueError("Freshness report requires a 'published' column.")

    total_rows = len(df)
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    published = pd.to_datetime(df["published"], errors="coerce", utc=True).dropna()

    report = {
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "stale_ratio": stale_ratio,
        "stale_ratio_percent": round(stale_ratio * 100, 2),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": 0.25,
        "latest_published": published.max().date().isoformat() if not published.empty else None,
        "oldest_published": published.min().date().isoformat() if not published.empty else None,
        "is_fresh": stale_ratio <= 0.25,
    }
    write_json(report_path, report)
    return report
