from __future__ import annotations

import pandas as pd

from core.config import load_settings
from observability.quality import build_freshness_report, run_data_quality_checks


if __name__ == "__main__":
    settings = load_settings()
    df = pd.read_json(settings.paths.clean_json)
    result = run_data_quality_checks(df, settings, stage="baseline")
    build_freshness_report(df, settings, settings.paths.freshness_report)
    print(f"Quality gate: success={result['success']}, GX={result['gx_success']}, fresh={result['is_fresh']}")
    print(f"Report: {settings.paths.baseline_quality_report}")
    raise SystemExit(0 if result["success"] else 1)
