from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Tao bo evaluation set tu cleaned dataframe phu du 4 nhom nghiep vu.

    1. Kiem tra so luong document toi thieu (>= 5).
    2. Chon 10 paper dai dien.
    3. Tao 4 loai cau hoi:
       - summary: Hoi ve noi dung chinh/cau dau cua summary
       - authors: Hoi ai la tac gia
       - date: Hoi ngay xuat ban
       - categories: Hoi ve chuyen nganh/linh vuc
    4. Moi cau hoi co cau truc:
       - id: eval_001 -> eval_010
       - question_type: summary / authors / date / categories
       - question: chua tieu de paper trong dau nhay don '<Title>'
       - ground_truth: noi dung chuan
       - ground_truth_doc_ids: [paper_id]
    5. Ghi file JSON vao output_path.
    """
    if len(df) < 5:
        raise ValueError(f"Can it nhat 5 document de tao test set, hien co: {len(df)}")

    # Phu du 4 loai cau hoi qua 10 cau
    question_type_cycle = [
        "summary",
        "authors",
        "date",
        "categories",
        "summary",
        "authors",
        "date",
        "categories",
        "summary",
        "authors",
    ]

    target_count = min(10, len(df))
    test_set: list[dict[str, Any]] = []

    for i in range(target_count):
        row = df.iloc[i]
        title = str(row["title"]).strip()
        paper_id = str(row["paper_id"]).strip()
        q_type = question_type_cycle[i % len(question_type_cycle)]

        if q_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))
        elif q_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = str(row["authors_joined"])
        elif q_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = str(row["published"])
        elif q_type == "categories":
            question = f"What categories does the paper '{title}' belong to?"
            ground_truth = str(row["categories_joined"])
        else:
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(str(row["summary"]))

        test_set.append(
            {
                "id": f"eval_{i + 1:03d}",
                "question_type": q_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    if output_path is not None:
        write_json(Path(output_path), test_set)

    return test_set
