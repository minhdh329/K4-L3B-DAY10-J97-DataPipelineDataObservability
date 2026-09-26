from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import write_csv, write_json
from ingestion.corruption import corrupt_clean_dataframe


if __name__ == "__main__":
    settings = load_settings()
    clean_df = pd.read_json(settings.paths.clean_json, convert_dates=False)
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    print(f"Corrupted {len(clean_df)} clean rows into {len(corrupted_df)} rows.")
    print(f"Corruption log: {settings.paths.corruption_log}")
