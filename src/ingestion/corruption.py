from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import math
from pathlib import Path

import pandas as pd

from core.utils import write_json


NOISE = "###NOISE### @@@ 0xDEADBEEF ??? "


def _refresh_text(row: dict) -> None:
    row["summary_chars"] = len(row["summary"])
    row["text_for_embedding"] = (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def corrupt_clean_dataframe(clean_df: pd.DataFrame, log_path) -> pd.DataFrame:
    """Inject six deterministic faults into a copy and log each row operation.

    Require at least five clean, uniquely identified rows. Drop ceil(20%) newest
    papers. Of the survivors, corrupt ceil(10%) summaries/titles per fault, age
    ceil(30%) by 365 days, then append ceil(10%) duplicate rows. Counts use the
    survivor count before duplication. Log positions are zero-based, independent
    of dataframe index labels; update snapshots reflect each operation in order.
    """
    required = {"paper_id", "title", "summary", "published", "age_days",
                "authors_joined", "categories_joined"}
    missing = sorted(required - set(clean_df.columns))
    if missing:
        raise ValueError(f"Missing clean columns: {', '.join(missing)}")
    if len(clean_df) < 5:
        raise ValueError("At least 5 clean rows are required to inject all six faults.")
    if clean_df["paper_id"].isna().any() or not clean_df["paper_id"].is_unique:
        raise ValueError("Input paper_id values must be non-null and unique.")
    for column in ("paper_id", "title", "summary", "authors_joined", "categories_joined"):
        if not clean_df[column].map(lambda value: isinstance(value, str)).all():
            raise ValueError(f"Clean column {column} must contain strings, not null values.")

    dates = pd.to_datetime(clean_df["published"], format="ISO8601", errors="raise", utc=True)
    ages = pd.to_numeric(clean_df["age_days"], errors="raise")
    if dates.isna().any() or ages.isna().any() or not ages.map(lambda value: math.isfinite(value)).all():
        raise ValueError("Published dates and ages must be valid and non-null.")
    rows = deepcopy(clean_df.to_dict(orient="records"))
    # Date values normally arrive as ISO strings from the clean snapshot.
    for position, row in enumerate(rows):
        row["published"] = dates.iloc[position].date().isoformat()
        row["age_days"] = int(ages.iloc[position])

    ordered = sorted(range(len(rows)), key=lambda pos: (-dates.iloc[pos].value, rows[pos]["paper_id"]))
    drop_count = math.ceil(len(rows) * 0.20)
    dropped = ordered[:drop_count]
    survivors = ordered[drop_count:]
    output_positions = {source: output for output, source in enumerate(survivors)}
    events = []

    def log_event(operation, source, before, after, output_position):
        events.append({
            "event_id": f"corruption_{len(events) + 1:03d}",
            "operation": operation,
            "paper_id": rows[source]["paper_id"],
            "source_position": source,
            "output_position": output_position,
            "before": deepcopy(before),
            "after": deepcopy(after),
        })

    for source in dropped:
        log_event("drop_latest_records", source, rows[source], None, None)

    edit_count = math.ceil(len(survivors) * 0.10)
    stale_count = math.ceil(len(survivors) * 0.30)
    groups = {
        "blank_summary": survivors[:edit_count],
        "inject_noise": survivors[edit_count:2 * edit_count],
        "truncate_title": survivors[2 * edit_count:3 * edit_count],
        "stale_date": [survivors[(3 * edit_count + offset) % len(survivors)]
                       for offset in range(stale_count)],
    }
    for operation, sources in groups.items():
        for source in sources:
            row = rows[source]
            before = deepcopy(row)
            if operation == "blank_summary":
                row["summary"] = ""
            elif operation == "inject_noise":
                row["summary"] = NOISE + row["summary"]
            elif operation == "truncate_title":
                row["title"] = row["title"][:min(7, max(0, len(row["title"]) - 1))]
            else:
                row["published"] = (dates.iloc[source].date() - timedelta(days=365)).isoformat()
                row["age_days"] += 365
            _refresh_text(row)
            log_event(operation, source, before, row, output_positions[source])

    output_rows = [rows[source] for source in survivors]
    for source in survivors[:edit_count]:
        duplicate = deepcopy(rows[source])
        log_event("duplicate_rows", source, rows[source], duplicate, len(output_rows))
        output_rows.append(duplicate)

    corrupted_df = pd.DataFrame(output_rows).reset_index(drop=True)
    operations = ["drop_latest_records", *groups, "duplicate_rows"]
    report = {
        "input_rows": len(clean_df),
        "output_rows": len(corrupted_df),
        "parameters": {"drop_fraction": 0.20, "edit_fraction": 0.10,
                       "stale_fraction": 0.30, "stale_shift_days": 365,
                       "duplicate_fraction": 0.10, "rounding": "ceil"},
        "counts": {operation: sum(event["operation"] == operation for event in events)
                   for operation in operations},
        "events": events,
    }
    write_json(Path(log_path), report)
    return corrupted_df
