from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import now_utc, write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str | None = None) -> pd.DataFrame:
    """Simulate 6 dang data corruption theo yeu cau bai lab:
    1. Drop latest records: Bo 20% cac ban ghi moi nhat.
    2. Blank summary: Xoa trang phan tom tat.
    3. Inject noise: Chen chuoi ky tu rac vo nghia vao summary.
    4. Truncate title: Cat ngan tieu de xuong duoi 8 ky tu.
    5. Stale date: Lui ngay xuat ban ve 365 ngay truoc (vi pham Freshness SLA).
    6. Duplicate rows: Nhan doi cac dong de tao trung lap (vi pham Uniqueness).
    7. Rebuild text_for_embedding va summary_chars.
    8. Ghi corruption log chi tiet vao output_log_path.
    """
    corrupted_df = df.copy()

    # 1. Drop 20% latest records
    drop_count = max(1, int(len(corrupted_df) * 0.2))
    dropped_records = corrupted_df.iloc[:drop_count]
    dropped_ids = dropped_records["paper_id"].astype(str).tolist()
    corrupted_df = corrupted_df.iloc[drop_count:].copy().reset_index(drop=True)

    # 2. Blank summary o 2 dong dau tien cua corrupted_df
    blank_count = min(2, len(corrupted_df))
    blank_ids = corrupted_df.iloc[:blank_count]["paper_id"].astype(str).tolist()
    for idx in range(blank_count):
        corrupted_df.loc[idx, "summary"] = ""
        corrupted_df.loc[idx, "summary_chars"] = 0

    # 3. Inject noise vao text o 2 dong tiep theo
    noise_start = blank_count
    noise_end = min(noise_start + 2, len(corrupted_df))
    noise_ids = corrupted_df.iloc[noise_start:noise_end]["paper_id"].astype(str).tolist()
    noise_payload = "###CORRUPTED_NOISE_GARBAGE_$%^&*!@# RANDOM_CHARS_123456789### "
    for idx in range(noise_start, noise_end):
        corrupted_df.loc[idx, "summary"] = noise_payload + str(corrupted_df.loc[idx, "summary"])

    # 4. Truncate title < 8 ky tu o 2 dong tiep theo
    trunc_start = noise_end
    trunc_end = min(trunc_start + 2, len(corrupted_df))
    trunc_ids = corrupted_df.iloc[trunc_start:trunc_end]["paper_id"].astype(str).tolist()
    for idx in range(trunc_start, trunc_end):
        corrupted_df.loc[idx, "title"] = str(corrupted_df.loc[idx, "title"])[:6]

    # 5. Stale date (lui 365 ngay ve qua khu cho 12 dong tiep theo de vi pham Freshness SLA > 25%)
    stale_start = trunc_end
    stale_end = min(stale_start + 12, len(corrupted_df))
    stale_ids = corrupted_df.iloc[stale_start:stale_end]["paper_id"].astype(str).tolist()
    for idx in range(stale_start, stale_end):
        try:
            pub_date = datetime.strptime(str(corrupted_df.loc[idx, "published"])[:10], "%Y-%m-%d").date()
            new_pub = pub_date - timedelta(days=365)
            corrupted_df.loc[idx, "published"] = new_pub.isoformat()
            if "age_days" in corrupted_df.columns:
                corrupted_df.loc[idx, "age_days"] = int(corrupted_df.loc[idx, "age_days"]) + 365
        except Exception:
            pass

    # 6. Add duplicate rows (nhan doi 2 dong de vi pham ExpectColumnValuesToBeUnique)
    dup_count = min(2, len(corrupted_df))
    dup_rows = corrupted_df.iloc[:dup_count].copy()
    dup_ids = dup_rows["paper_id"].astype(str).tolist()
    corrupted_df = pd.concat([corrupted_df, dup_rows], ignore_index=True)

    # 7. Rebuild summary_chars va text_for_embedding
    corrupted_df["summary_chars"] = corrupted_df["summary"].astype(str).str.len()
    corrupted_df["text_for_embedding"] = (
        "Title: " + corrupted_df["title"].astype(str) + "\n"
        "Authors: " + corrupted_df["authors_joined"].astype(str) + "\n"
        "Published: " + corrupted_df["published"].astype(str) + "\n"
        "Categories: " + corrupted_df["categories_joined"].astype(str) + "\n"
        "Summary: " + corrupted_df["summary"].astype(str)
    )

    # 8. Ghi corruption log vao output_log_path
    corruption_log = {
        "timestamp": now_utc().isoformat(),
        "input_records_count": len(df),
        "corrupted_records_count": len(corrupted_df),
        "scenarios": [
            {
                "type": "drop_latest_records",
                "description": "Drop 20% cac ban ghi moi nhat (mat du lieu tuoi)",
                "affected_count": len(dropped_ids),
                "affected_paper_ids": dropped_ids,
            },
            {
                "type": "blank_summary",
                "description": "Xoa trang phan summary (mo phong loi cao du lieu rong)",
                "affected_count": len(blank_ids),
                "affected_paper_ids": blank_ids,
            },
            {
                "type": "inject_noise",
                "description": "Chen chuoi ky tu rac vo nghia vao summary",
                "affected_count": len(noise_ids),
                "affected_paper_ids": noise_ids,
            },
            {
                "type": "truncate_title",
                "description": "Cat ngan tieu de xuong duoi 8 ky tu",
                "affected_count": len(trunc_ids),
                "affected_paper_ids": trunc_ids,
            },
            {
                "type": "stale_date",
                "description": "Lui ngay xuat ban ve 365 ngay truoc (vi pham Freshness SLA)",
                "affected_count": len(stale_ids),
                "affected_paper_ids": stale_ids,
            },
            {
                "type": "duplicate_rows",
                "description": "Nhan doi cac dong de tao du lieu trung lap (vi pham tinh duy nhat)",
                "affected_count": len(dup_ids),
                "affected_paper_ids": dup_ids,
            },
        ],
    }

    if output_log_path is not None:
        write_json(Path(output_log_path), corruption_log)

    return corrupted_df
