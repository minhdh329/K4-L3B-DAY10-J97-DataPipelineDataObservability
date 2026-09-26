from __future__ import annotations

from datetime import datetime
import re

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records and prepare text for embedding."""
    rows = []
    for record in records:
        title = _normalize_text(record.title)
        summary = _normalize_text(record.summary)
        paper_id = _normalize_text(record.paper_id)
        published = _parse_date(record.published)
        updated = _parse_date(record.updated)
        authors = [_normalize_text(author) for author in record.authors]
        categories = [_normalize_text(category) for category in record.categories]
        authors = [author for author in authors if author]
        categories = [category for category in categories if category]

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": _normalize_text(record.primary_category),
                "published": published,
                "updated": updated,
                "abs_url": _normalize_text(record.abs_url),
                "pdf_url": _normalize_text(record.pdf_url),
                "comment": _normalize_text(record.comment),
            }
        )

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return _empty_dataframe()

    dataframe["published"] = pd.to_datetime(dataframe["published"], errors="coerce")
    dataframe["updated"] = pd.to_datetime(dataframe["updated"], errors="coerce")
    run_timestamp = pd.Timestamp(run_date).tz_localize(None)
    dataframe["age_days"] = (run_timestamp.normalize() - dataframe["published"]).dt.days
    dataframe["authors_joined"] = dataframe["authors"].map(
        lambda authors: ", ".join(authors)
    )
    dataframe["categories_joined"] = dataframe["categories"].map(
        lambda categories: ", ".join(categories)
    )
    dataframe["summary_chars"] = dataframe["summary"].str.len()
    dataframe["text_for_embedding"] = dataframe.apply(
        lambda row: "\n".join(
            [
                f"Title: {row['title']}",
                f"Authors: {row['authors_joined']}",
                f"Published: {row['published'].date().isoformat() if pd.notna(row['published']) else ''}",
                f"Categories: {row['categories_joined']}",
                f"Summary: {row['summary']}",
            ]
        ),
        axis=1,
    )

    dataframe = dataframe[
        (dataframe["paper_id"] != "")
        & (dataframe["title"] != "")
        & (dataframe["summary"] != "")
        & dataframe["published"].notna()
    ]
    dataframe = dataframe.drop_duplicates(subset=["paper_id"], keep="first")
    return dataframe.sort_values(
        ["published", "paper_id"], ascending=[False, True]
    ).reset_index(drop=True)


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_date(value: object) -> str:
    return str(value or "").strip()[:10]


def _empty_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "paper_id",
            "title",
            "summary",
            "authors",
            "categories",
            "primary_category",
            "published",
            "updated",
            "abs_url",
            "pdf_url",
            "comment",
            "age_days",
            "authors_joined",
            "categories_joined",
            "summary_chars",
            "text_for_embedding",
        ]
    )
