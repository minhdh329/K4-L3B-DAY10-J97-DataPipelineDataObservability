from __future__ import annotations

from math import ceil

import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Apply six deterministic data-failure scenarios and persist their lineage.

    The function never mutates the clean baseline dataframe.  Stable row
    selection lets repeated runs produce the same corrupted state and log,
    which is essential for a meaningful baseline/corrupted/repaired comparison.
    """
    required_columns = {
        "paper_id", "title", "summary", "published", "age_days",
        "authors_joined", "categories_joined",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {sorted(missing_columns)}")
    if len(df) < 10:
        raise ValueError("At least 10 rows are required for the corruption suite.")

    corrupted = df.copy(deep=True).sort_values("paper_id", kind="stable").reset_index(drop=True)
    log: list[dict[str, object]] = []

    # 1. Remove 20% of the most recently published papers.
    newest_count = max(1, ceil(len(corrupted) * 0.20))
    newest_indices = corrupted.assign(
        _published=pd.to_datetime(corrupted["published"], errors="coerce")
    ).nlargest(newest_count, "_published").index
    dropped_ids = corrupted.loc[newest_indices, "paper_id"].astype(str).tolist()
    corrupted = corrupted.drop(index=newest_indices).reset_index(drop=True)
    log.append(
        {
            "corruption": "drop_latest_records",
            "affected_rows": len(dropped_ids),
            "paper_ids": dropped_ids,
            "parameters": {"fraction": 0.20, "selection": "most_recent_published"},
        }
    )

    # Allocate disjoint records to make each failure visible in its own field.
    blank_indices = list(range(0, 2))
    noise_indices = list(range(2, 4))
    truncate_indices = list(range(4, 6))
    stale_indices = list(range(6, min(12, len(corrupted))))

    # 2. Remove summary content.
    blank_ids = corrupted.loc[blank_indices, "paper_id"].astype(str).tolist()
    corrupted.loc[blank_indices, "summary"] = ""
    corrupted.loc[blank_indices, "summary_chars"] = 0
    log.append(
        {
            "corruption": "blank_summary",
            "affected_rows": len(blank_ids),
            "paper_ids": blank_ids,
            "parameters": {"replacement": ""},
        }
    )

    # 3. Add clearly non-semantic tokens that damage embedding input.
    noise_marker = " @@#NOISE_9X!$%@@ "
    noise_ids = corrupted.loc[noise_indices, "paper_id"].astype(str).tolist()
    corrupted.loc[noise_indices, "summary"] = (
        corrupted.loc[noise_indices, "summary"].astype(str) + noise_marker
    )
    corrupted.loc[noise_indices, "summary_chars"] = corrupted.loc[noise_indices, "summary"].str.len()
    log.append(
        {
            "corruption": "inject_noise",
            "affected_rows": len(noise_ids),
            "paper_ids": noise_ids,
            "parameters": {"marker": noise_marker.strip()},
        }
    )

    # 4. Make titles invalid for the title-length quality contract.
    truncate_ids = corrupted.loc[truncate_indices, "paper_id"].astype(str).tolist()
    corrupted.loc[truncate_indices, "title"] = corrupted.loc[truncate_indices, "title"].astype(str).str.slice(0, 7)
    log.append(
        {
            "corruption": "truncate_title",
            "affected_rows": len(truncate_ids),
            "paper_ids": truncate_ids,
            "parameters": {"max_length": 7},
        }
    )

    # 5. Age enough documents by a year to breach the 25% freshness SLA.
    stale_ids = corrupted.loc[stale_indices, "paper_id"].astype(str).tolist()
    stale_dates = pd.to_datetime(corrupted.loc[stale_indices, "published"], errors="coerce") - pd.Timedelta(days=365)
    corrupted.loc[stale_indices, "published"] = stale_dates.dt.date.astype(str)
    corrupted.loc[stale_indices, "age_days"] = (
        pd.to_numeric(corrupted.loc[stale_indices, "age_days"], errors="coerce").fillna(0).astype(int) + 365
    )
    log.append(
        {
            "corruption": "stale_date",
            "affected_rows": len(stale_ids),
            "paper_ids": stale_ids,
            "parameters": {"days_shifted_back": 365},
        }
    )

    # 6. Append exact copies so the document-identity uniqueness check fails.
    duplicate_source_indices = list(range(len(corrupted) - 2, len(corrupted)))
    duplicate_ids = corrupted.loc[duplicate_source_indices, "paper_id"].astype(str).tolist()
    duplicated_rows = corrupted.loc[duplicate_source_indices].copy()
    corrupted = pd.concat([corrupted, duplicated_rows], ignore_index=True)
    log.append(
        {
            "corruption": "duplicate_rows",
            "affected_rows": len(duplicate_ids),
            "paper_ids": duplicate_ids,
            "parameters": {"copies_per_record": 1},
        }
    )

    corrupted["text_for_embedding"] = (
        "Title: " + corrupted["title"].astype(str)
        + "\nAuthors: " + corrupted["authors_joined"].astype(str)
        + "\nPublished: " + corrupted["published"].astype(str)
        + "\nCategories: " + corrupted["categories_joined"].astype(str)
        + "\nSummary: " + corrupted["summary"].astype(str)
    )
    write_json(output_log_path, log)
    return corrupted.reset_index(drop=True)
