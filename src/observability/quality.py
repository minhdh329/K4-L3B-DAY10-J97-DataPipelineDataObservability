from __future__ import annotations

from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import now_utc, safe_slug, write_json


def evaluate_freshness_sla(
    df: pd.DataFrame, threshold_days: int = 180, max_stale_ratio: float = 0.25,
) -> dict[str, Any]:
    """Exactly 180 days is fresh; exactly 25% stale still meets the SLA.

    Empty data or unknown/nonfinite ages cannot establish freshness and fail.
    """
    if threshold_days < 0 or not 0 <= max_stale_ratio <= 1:
        raise ValueError("Invalid freshness threshold or stale ratio.")
    total_rows = len(df)
    ages = pd.to_numeric(
        df["age_days"] if "age_days" in df else pd.Series(index=df.index, dtype=float),
        errors="coerce",
    )
    valid = ages.notna() & ages.abs().ne(float("inf"))
    invalid_age_rows = int((~valid).sum())
    stale_rows = int((valid & ages.gt(threshold_days)).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0
    return {
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "stale_ratio": stale_ratio,
        "invalid_age_rows": invalid_age_rows,
        "threshold_days": threshold_days,
        "max_stale_ratio": max_stale_ratio,
        "is_fresh": bool(total_rows and not invalid_age_rows and stale_ratio <= max_stale_ratio),
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, stage: str) -> dict[str, Any]:
    """Validate a copy with GX 1.x and return a gate combining GX and freshness.

    Callers must check success before indexing. Blank strings count as null;
    summary also needs a not-null check because GX length checks skip nulls.
    Save a JSON report for each stage without changing the input dataframe.
    """
    freshness = evaluate_freshness_sla(df, threshold_days=settings.freshness_threshold_days)
    required_columns = ["paper_id", "title", "text_for_embedding", "summary"]
    missing_columns = [column for column in required_columns if column not in df]
    validation = {"success": False, "results": [], "statistics": {}}
    if not missing_columns:
        validation_df = df.copy(deep=True)
        for column in required_columns:
            validation_df[column] = validation_df[column].replace(r"^\s*$", None, regex=True)

        context = gx.get_context(mode="ephemeral")
        data_source = context.data_sources.add_pandas(name="papers_source")
        data_asset = data_source.add_dataframe_asset(name="papers_asset")
        batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
        batch = batch_def.get_batch(batch_parameters={"dataframe": validation_df})
        expectations = [gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)]
        expectations.extend(
            gx.expectations.ExpectColumnValuesToNotBeNull(column=column)
            for column in required_columns
        )
        expectations.extend([
            gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
            gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
        ])
        suite = gx.ExpectationSuite(name="papers_quality", expectations=expectations)
        validation = batch.validate(suite).to_json_dict()

    report = {
        "stage": stage,
        "checked_at": now_utc().isoformat(),
        "row_count": len(df),
        "success": bool(validation["success"] and freshness["is_fresh"]),
        "gx_success": bool(validation["success"]),
        "is_fresh": freshness["is_fresh"],
        "missing_columns": missing_columns,
        "freshness": freshness,
        "statistics": validation["statistics"],
        "results": validation["results"],
    }
    write_json(settings.paths.quality_dir / f"{safe_slug(stage)}_quality_report.json", report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Save the same freshness SLA with the publication date range."""
    report = evaluate_freshness_sla(df, threshold_days=settings.freshness_threshold_days)
    published = pd.to_datetime(df.get("published", pd.Series(dtype=str)), errors="coerce", utc=True)
    valid_dates = published.dropna()
    report.update({
        "latest_published": valid_dates.max().date().isoformat() if len(valid_dates) else None,
        "oldest_published": valid_dates.min().date().isoformat() if len(valid_dates) else None,
    })
    write_json(report_path, report)
    return report
