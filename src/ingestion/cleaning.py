from __future__ import annotations

from datetime import datetime
import re

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Return an embedding-ready dataframe derived from raw Crossref records.

    The returned schema is consumed by the retrieval, evaluation, and quality
    modules, so this function keeps both normalized source fields and helper
    fields such as ``authors_joined`` and ``text_for_embedding``.
    """
    columns = [
        "paper_id", "title", "summary", "authors", "categories",
        "primary_category", "published", "updated", "abs_url", "pdf_url",
        "comment", "authors_joined", "categories_joined", "summary_chars",
        "age_days", "text_for_embedding",
    ]

    def normalize_text(value: object) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def normalize_list(values: object) -> list[str]:
        if not isinstance(values, (list, tuple)):
            return []
        return [text for value in values if (text := normalize_text(value))]

    rows: list[dict[str, object]] = []
    for record in records:
        paper_id = normalize_text(record.paper_id).lower()
        title = normalize_text(record.title)
        summary = normalize_text(record.summary)
        published = pd.to_datetime(record.published, errors="coerce", utc=True)

        # A record with no stable identifier, embedding content, or publication
        # date cannot be evaluated for duplicate handling or freshness.
        if not paper_id or not title or not summary or pd.isna(published):
            continue

        authors = normalize_list(record.authors)
        categories = normalize_list(record.categories)
        authors_joined = ", ".join(authors) or "Unknown"
        categories_joined = ", ".join(categories) or "Uncategorized"
        published_date = published.date().isoformat()
        updated = pd.to_datetime(record.updated, errors="coerce", utc=True)
        updated_date = updated.date().isoformat() if not pd.isna(updated) else published_date

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_text(record.primary_category) or "Uncategorized",
                "published": published_date,
                "updated": updated_date,
                "abs_url": normalize_text(record.abs_url),
                "pdf_url": normalize_text(record.pdf_url),
                "comment": normalize_text(record.comment),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    # DOI is case-insensitive.  Keeping the first occurrence preserves the
    # original source record while eliminating duplicate documents in the index.
    df = df.drop_duplicates(subset="paper_id", keep="first").copy()

    published_at = pd.to_datetime(df["published"], utc=True)
    run_at = pd.Timestamp(run_date)
    if run_at.tzinfo is None:
        run_at = run_at.tz_localize("UTC")
    else:
        run_at = run_at.tz_convert("UTC")
    df["age_days"] = (run_at.normalize() - published_at.dt.normalize()).dt.days.astype(int)

    df["text_for_embedding"] = (
        "Title: " + df["title"]
        + "\nAuthors: " + df["authors_joined"]
        + "\nPublished: " + df["published"]
        + "\nCategories: " + df["categories_joined"]
        + "\nSummary: " + df["summary"]
    )
    return df.sort_values("paper_id", kind="stable").reset_index(drop=True)[columns]
