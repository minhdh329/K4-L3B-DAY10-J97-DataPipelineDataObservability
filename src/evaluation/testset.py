from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


MISSING_CATEGORIES = "Not provided in source metadata."


def _text(value: Any) -> str:
    return normalize_whitespace(value) if isinstance(value, str) else ""


def _joined(row: dict, field: str) -> str:
    joined = _text(row.get(f"{field}_joined"))
    if joined:
        return joined
    values = row.get(field)
    if isinstance(values, list):
        return ", ".join(text for value in values if (text := _text(value)))
    return ""


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build 10 deterministic questions: 3 summaries, 3 authors, 2 dates, 2 categories.

    Prefer distinct papers, never repeat a (type, DOI) pair, and use only source
    metadata for answers. Unknown categories have an explicit absence answer.
    Require at least 3 unique titled papers and enough valid answers per type;
    fail before writing if the input cannot produce the complete test set.
    """
    required = {"paper_id", "title", "summary", "published"}
    missing = sorted(required - set(df.columns))
    for field in ("authors", "categories"):
        if field not in df and f"{field}_joined" not in df:
            missing.append(f"{field} or {field}_joined")
    if missing:
        raise ValueError(f"Missing columns for evaluation: {', '.join(missing)}")

    papers = {}
    for row in df.to_dict(orient="records"):
        paper_id, title = _text(row["paper_id"]), _text(row["title"])
        if not paper_id or not title or paper_id in papers:
            continue
        published = _text(row["published"])
        try:
            published = date.fromisoformat(published).isoformat()
        except ValueError:
            published = ""
        papers[paper_id] = {
            "paper_id": paper_id,
            "title": title,
            "summary": first_sentence(_text(row["summary"])),
            "authors": _joined(row, "authors"),
            "date": published,
            "categories": _joined(row, "categories"),
        }
    if len(papers) < 3:
        raise ValueError("At least 3 unique papers with paper_id and title are required.")

    order = ["summary", "authors", "date", "categories"] * 2 + ["summary", "authors"]
    quotas = Counter(order)
    candidates = {}
    for kind, count in quotas.items():
        pool = [paper for _, paper in sorted(papers.items()) if paper[kind] or kind == "categories"]
        if kind == "categories":
            known = [paper for paper in pool if paper[kind]]
            # Use actual categories whenever enough papers provide them.
            pool = known if len(known) >= count else known + [paper for paper in pool if not paper[kind]]
        if len(pool) < count:
            raise ValueError(f"Need {count} papers with valid {kind} metadata; found {len(pool)}.")
        candidates[kind] = pool

    templates = {
        "summary": "What is the summary of the paper '{title}'?",
        "authors": "Who authored the paper '{title}'?",
        "date": "When was the paper '{title}' published?",
        "categories": "What categories are listed in the source metadata for the paper '{title}'?",
    }
    test_set = []
    used_ids: set[str] = set()
    for number, kind in enumerate(order, start=1):
        pool = candidates[kind]
        paper = next((paper for paper in pool if paper["paper_id"] not in used_ids), pool[0])
        pool.remove(paper)
        used_ids.add(paper["paper_id"])
        test_set.append({
            "id": f"eval_{number:03d}",
            "question_type": kind,
            "question": templates[kind].format(title=paper["title"]),
            "ground_truth": paper[kind] or MISSING_CATEGORIES,
            "ground_truth_doc_ids": [paper["paper_id"]],
        })
    write_json(Path(output_path), test_set)
    return test_set
