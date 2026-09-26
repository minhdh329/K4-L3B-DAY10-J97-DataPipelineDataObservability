from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create a deterministic, 10-question ground-truth benchmark.

    Sorting by ``paper_id`` means baseline, corruption, and repair runs use the
    same questions and ground-truth documents, making their metrics comparable.
    Ten questions cannot divide equally among four categories, so the round-
    robin allocation is 3 summary, 3 authors, 2 date, and 2 categories.
    """
    required_columns = {
        "paper_id", "title", "summary", "authors_joined", "published", "categories_joined"
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {sorted(missing_columns)}")

    candidates = df.dropna(subset=list(required_columns)).copy()
    candidates = candidates.sort_values("paper_id", kind="stable")
    if len(candidates) < 10:
        raise ValueError("At least 10 clean documents are required to build the evaluation set.")

    question_types = [
        "summary", "authors", "date", "categories",
        "summary", "authors", "date", "categories",
        "summary", "authors",
    ]
    test_set: list[dict[str, Any]] = []
    for index, (_, row) in enumerate(candidates.head(10).iterrows(), start=1):
        paper_id = normalize_whitespace(str(row["paper_id"]))
        title = normalize_whitespace(str(row["title"]))
        question_type = question_types[index - 1]

        if question_type == "summary":
            question = f'What is the summary of the paper "{title}"?'
            ground_truth = first_sentence(normalize_whitespace(str(row["summary"])))
        elif question_type == "authors":
            question = f'Who are the authors of the paper "{title}"?'
            ground_truth = normalize_whitespace(str(row["authors_joined"]))
        elif question_type == "date":
            question = f'When was the paper "{title}" published?'
            ground_truth = normalize_whitespace(str(row["published"]))
        else:
            question = f'What are the research categories of the paper "{title}"?'
            ground_truth = normalize_whitespace(str(row["categories_joined"]))

        if not all((paper_id, title, ground_truth)):
            raise ValueError(f"Document at benchmark position {index} has an empty required value.")
        test_set.append(
            {
                "id": f"eval_{index:03d}",
                "question_type": question_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    write_json(output_path, test_set)
    return test_set
