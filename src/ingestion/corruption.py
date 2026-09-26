from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Apply deterministic data corruption scenarios and write an audit log."""
    corrupted = df.copy(deep=True)
    operations: list[dict[str, object]] = []

    if corrupted.empty:
        _write_log(output_log_path, len(df), corrupted, operations)
        return corrupted

    corrupted["published"] = pd.to_datetime(corrupted["published"], errors="coerce")
    drop_count = max(1, round(len(corrupted) * 0.20))
    latest_ids = corrupted.nlargest(drop_count, "published")["paper_id"].astype(str).tolist()
    corrupted = corrupted[~corrupted["paper_id"].isin(latest_ids)].reset_index(drop=True)
    operations.append(
        {"type": "drop_latest_records", "count": len(latest_ids), "paper_ids": latest_ids}
    )

    target_count = max(1, round(len(corrupted) * 0.10))
    blank_ids = corrupted.head(target_count)["paper_id"].astype(str).tolist()
    corrupted.loc[corrupted["paper_id"].isin(blank_ids), "summary"] = ""
    operations.append(
        {"type": "blank_summary", "count": len(blank_ids), "paper_ids": blank_ids}
    )

    noise_ids = corrupted.iloc[target_count : target_count * 2]["paper_id"].astype(str).tolist()
    corrupted.loc[corrupted["paper_id"].isin(noise_ids), "summary"] = corrupted.loc[
        corrupted["paper_id"].isin(noise_ids), "summary"
    ].map(lambda value: f"[CORRUPTED_NOISE] {value}")
    operations.append(
        {"type": "inject_noise", "count": len(noise_ids), "paper_ids": noise_ids}
    )

    truncate_ids = corrupted.iloc[target_count * 2 : target_count * 3]["paper_id"].astype(str).tolist()
    corrupted.loc[corrupted["paper_id"].isin(truncate_ids), "title"] = corrupted.loc[
        corrupted["paper_id"].isin(truncate_ids), "title"
    ].map(lambda value: str(value)[:8])
    operations.append(
        {"type": "truncate_title", "count": len(truncate_ids), "paper_ids": truncate_ids}
    )

    stale_ids = corrupted.iloc[target_count * 3 : target_count * 4]["paper_id"].astype(str).tolist()
    corrupted.loc[corrupted["paper_id"].isin(stale_ids), "published"] = corrupted.loc[
        corrupted["paper_id"].isin(stale_ids), "published"
    ] - pd.Timedelta(days=365)
    operations.append(
        {"type": "stale_date", "count": len(stale_ids), "paper_ids": stale_ids}
    )

    duplicate_source = corrupted.head(max(1, target_count)).copy()
    corrupted = pd.concat([corrupted, duplicate_source], ignore_index=True)
    operations.append(
        {
            "type": "duplicate_rows",
            "count": len(duplicate_source),
            "paper_ids": duplicate_source["paper_id"].astype(str).tolist(),
        }
    )

    corrupted["updated"] = pd.to_datetime(corrupted["updated"], errors="coerce")
    corrupted["age_days"] = (
        pd.Timestamp.utcnow().tz_localize(None).normalize() - corrupted["published"]
    ).dt.days
    corrupted["authors_joined"] = corrupted["authors"].map(
        lambda authors: ", ".join(authors) if isinstance(authors, list) else str(authors)
    )
    corrupted["categories_joined"] = corrupted["categories"].map(
        lambda categories: ", ".join(categories) if isinstance(categories, list) else str(categories)
    )
    corrupted["summary_chars"] = corrupted["summary"].fillna("").str.len()
    corrupted["text_for_embedding"] = corrupted.apply(_embedding_text, axis=1)
    _write_log(output_log_path, len(df), corrupted, operations)
    return corrupted


def _embedding_text(row: pd.Series) -> str:
    published = row["published"]
    published_text = published.date().isoformat() if pd.notna(published) else ""
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {published_text}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def _write_log(output_log_path, input_rows: int, corrupted: pd.DataFrame, operations: list[dict[str, object]]) -> None:
    path = Path(output_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input_rows": input_rows,
        "output_rows": len(corrupted),
        "operations": operations,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
