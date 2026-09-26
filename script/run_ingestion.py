from __future__ import annotations

from core.config import load_settings
from ingestion.crossref import fetch_source_records


if __name__ == "__main__":
    settings = load_settings()
    records = fetch_source_records(settings)
    print(f"Fetched {len(records)} Crossref papers.")
    print(f"API response: {settings.paths.raw_api_response}")
    print(f"Paper records: {settings.paths.raw_records_json}")
