from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records


if __name__ == "__main__":
    settings = load_settings()
    records = load_raw_records(settings.paths.raw_records_json)
    run_date = now_utc()
    df = build_clean_dataframe(records, run_date)
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    print(f"Cleaned {len(records)} raw records into {len(df)} unique papers at {run_date.isoformat()}.")
    print(f"Clean CSV: {settings.paths.clean_csv}")
    print(f"Clean JSON: {settings.paths.clean_json}")
