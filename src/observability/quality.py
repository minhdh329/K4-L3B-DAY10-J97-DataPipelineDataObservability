from datetime import datetime
from pathlib import Path
from typing import Any

import great_expectations as gx
from great_expectations.expectations import (
    ExpectColumnValueLengthsToBeBetween,
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToNotBeNull,
    ExpectTableRowCountToBeBetween,
)
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tao bo data quality checks voi Great Expectations 1.x va Freshness SLA.

    1. Check row count bang ExpectTableRowCountToBeBetween.
    2. Check paper_id not null va unique, title va text_for_embedding not null.
    3. Check do dai summary bang ExpectColumnValueLengthsToBeBetween.
    4. Check freshness bang age_days (SLA <= 25% stale).
    5. Ghi ket qua vao data/quality/.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=f"papers_quality_suite_{report_name}")
    suite.add_expectation(ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    val_res = batch.validate(suite)
    gx_success = bool(val_res.success)

    freshness_path = (
        settings.paths.freshness_report
        if report_name == "baseline"
        else settings.paths.quality_dir / f"{report_name}_freshness_report.json"
    )
    freshness = build_freshness_report(df, settings, freshness_path)
    is_fresh = bool(freshness["is_fresh"])

    overall_success = bool(gx_success and is_fresh)

    val_dict = val_res.to_json_dict()
    report = {
        "report_name": report_name,
        "success": overall_success,
        "gx_success": gx_success,
        "is_fresh": is_fresh,
        "freshness": freshness,
        "statistics": val_dict.get("statistics", {}),
        "results": val_dict.get("results", []),
    }

    if report_name == "baseline":
        out_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        out_path = settings.paths.corrupted_quality_report
    else:
        out_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    write_json(out_path, report)
    return report


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: Path | str | None = None
) -> dict[str, Any]:
    """Tong hop freshness report theo Freshness SLA (age_days > 180 khong vuot qua 25%).

    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - stale_ratio
       - is_fresh
    4. Ghi JSON report neu report_path hop le.
    """
    total_rows = len(df)
    threshold_days = settings.freshness_threshold_days

    if total_rows == 0:
        stale_rows = 0
        stale_ratio = 1.0
        is_fresh = False
        latest_published = ""
        oldest_published = ""
    else:
        if "age_days" in df.columns:
            stale_rows = int((df["age_days"] > threshold_days).sum())
        elif "published" in df.columns:
            run_date = now_utc().date()
            stale_count = 0
            for val in df["published"]:
                try:
                    pub_d = datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
                    if (run_date - pub_d).days > threshold_days:
                        stale_count += 1
                except Exception:
                    stale_count += 1
            stale_rows = stale_count
        else:
            stale_rows = total_rows

        stale_ratio = stale_rows / total_rows
        is_fresh = bool(stale_ratio <= 0.25)

        pub_dates = [str(x) for x in df.get("published", pd.Series(dtype=object)).dropna() if str(x).strip()]
        latest_published = max(pub_dates) if pub_dates else ""
        oldest_published = min(pub_dates) if pub_dates else ""

    report = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": int(stale_rows),
        "total_rows": int(total_rows),
        "stale_ratio": round(float(stale_ratio), 4),
        "freshness_threshold_days": threshold_days,
        "is_fresh": is_fresh,
    }

    if report_path is not None:
        write_json(Path(report_path), report)

    return report
