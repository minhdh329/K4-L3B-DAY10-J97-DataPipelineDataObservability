from __future__ import annotations

from dataclasses import asdict, fields
from datetime import UTC, date, datetime, time

import pandas as pd

from ingestion.crossref import PaperRecord
from core.utils import normalize_whitespace


def _normalize(value: str) -> str:
    return normalize_whitespace(value) if isinstance(value, str) else ""


def _normalize_list(values: list[str]) -> list[str]:
    return list(dict.fromkeys(text for value in (values or []) if (text := _normalize(value))))


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(_normalize(value))
    except ValueError:
        return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize records without modifying the raw data.

    Keep the first valid record per normalized DOI. Skip missing IDs/titles or
    invalid publication dates; preserve empty optional metadata and future dates.
    Dates are ISO calendar dates, interpreted at midnight UTC for age_days.
    A naive run_date is treated as UTC. Return newest publications first.
    """
    run_date = run_date.replace(tzinfo=UTC) if run_date.tzinfo is None else run_date.astimezone(UTC)
    rows = []
    seen = set()
    for record in records:
        row = asdict(record)
        for key, value in row.items():
            if key not in {"authors", "categories"}:
                row[key] = _normalize(value)
        row["paper_id"] = row["paper_id"].lower()
        published = _parse_date(row["published"])
        if not row["paper_id"] or not row["title"] or published is None:
            continue
        if row["paper_id"] in seen:
            continue
        seen.add(row["paper_id"])

        row["authors"] = _normalize_list(row["authors"])
        row["categories"] = _normalize_list(row["categories"])
        row["primary_category"] = row["categories"][0] if row["categories"] else ""
        row["published"] = published.isoformat()
        updated = _parse_date(row["updated"]) or published
        row["updated"] = updated.isoformat()
        row["age_days"] = (run_date - datetime.combine(published, time.min, tzinfo=UTC)).days
        row["authors_joined"] = ", ".join(row["authors"])
        row["categories_joined"] = ", ".join(row["categories"])
        row["summary_chars"] = len(row["summary"])
        row["text_for_embedding"] = (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        )
        rows.append(row)

    columns = [field.name for field in fields(PaperRecord)] + [
        "age_days", "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    ]
    df = pd.DataFrame(rows, columns=columns).astype({"age_days": "int64", "summary_chars": "int64"})
    return df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
