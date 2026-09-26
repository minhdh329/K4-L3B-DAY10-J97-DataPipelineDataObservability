from __future__ import annotations

from datetime import datetime
import re

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days = (run_date - published).days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding (cấu trúc 5 phần: Title, Authors, Published, Categories, Summary)
    5. Drop duplicates va filter row xau.
    6. Sort dataframe va return.
    """
    run_date_obj = run_date.date() if isinstance(run_date, datetime) else run_date

    rows: list[dict] = []
    for r in records:
        paper_id = r.paper_id.strip() if r.paper_id else ""
        title = normalize_whitespace(re.sub(r"<[^>]+>", " ", r.title)) if r.title else ""
        summary = normalize_whitespace(re.sub(r"<[^>]+>", " ", r.summary)) if r.summary else ""

        # Filter row xau (thieu paper_id, title, hoac summary)
        if not paper_id or not title or not summary:
            continue

        authors = [normalize_whitespace(a) for a in (r.authors or []) if a and a.strip()]
        authors_joined = ", ".join(authors)

        categories = [normalize_whitespace(c) for c in (r.categories or []) if c and c.strip()]
        categories_joined = ", ".join(categories)

        primary_category = (
            r.primary_category.strip()
            if r.primary_category and r.primary_category.strip()
            else (categories[0] if categories else "Unknown")
        )

        pub_str = (r.published or "").strip()
        try:
            pub_date = datetime.strptime(pub_str[:10], "%Y-%m-%d").date()
            published_clean = pub_date.isoformat()
        except Exception:
            pub_date = datetime(1970, 1, 1).date()
            published_clean = "1970-01-01"

        age_days = int((run_date_obj - pub_date).days)

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published_clean}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published_clean,
                "updated": (r.updated or "").strip() or published_clean,
                "abs_url": (r.abs_url or "").strip(),
                "pdf_url": (r.pdf_url or "").strip(),
                "comment": (r.comment or "").strip(),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    if not rows:
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
                "authors_joined",
                "categories_joined",
                "summary_chars",
                "age_days",
                "text_for_embedding",
            ]
        )

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df

