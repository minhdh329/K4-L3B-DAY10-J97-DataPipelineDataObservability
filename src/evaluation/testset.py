from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a ten-question benchmark from the cleaned dataframe."""
    if len(df) < 4:
        raise ValueError("At least 4 documents are required to build the test set.")

    required_columns = {"paper_id", "title", "summary", "published"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(f"DataFrame is missing required columns: {sorted(missing_columns)}")

    rows = df.drop_duplicates(subset=["paper_id"]).reset_index(drop=True)
    if len(rows) < 4:
        raise ValueError("At least 4 unique paper_id values are required.")

    question_types = ["summary"] * 3 + ["authors"] * 3 + ["date"] * 2 + ["categories"] * 2
    test_set: list[dict[str, Any]] = []
    for index, question_type in enumerate(question_types):
        row = rows.iloc[index % len(rows)]
        paper_id = _text(row["paper_id"])
        title = _text(row["title"])
        ground_truth = _ground_truth(row, question_type)
        test_set.append(
            {
                "id": f"eval_{index + 1:03d}",
                "question_type": question_type,
                "question": _question(question_type, title),
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(test_set, ensure_ascii=False, indent=2), encoding="utf-8")
    return test_set


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _question(question_type: str, title: str) -> str:
    prompts = {
        "summary": f"What is the summary of the paper '{title}'?",
        "authors": f"Who are the authors of the paper '{title}'?",
        "date": f"When was the paper '{title}' published?",
        "categories": f"What categories does the paper '{title}' belong to?",
    }
    return prompts[question_type]


def _ground_truth(row: pd.Series, question_type: str) -> str:
    if question_type == "summary":
        return _text(row["summary"])
    if question_type == "authors":
        if "authors_joined" in row.index and _text(row["authors_joined"]):
            return _text(row["authors_joined"])
        authors = row.get("authors", [])
        return ", ".join(str(author).strip() for author in authors if str(author).strip())
    if question_type == "date":
        return _text(row["published"])[:10]
    categories = _text(row.get("categories_joined", ""))
    if categories:
        return categories
    primary_category = _text(row.get("primary_category", ""))
    return primary_category or "No categories listed."
