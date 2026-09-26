from __future__ import annotations

from collections import Counter

import pandas as pd

from core.config import load_settings
from evaluation.testset import build_test_set


if __name__ == "__main__":
    settings = load_settings()
    df = pd.read_json(settings.paths.clean_json, convert_dates=False)
    questions = build_test_set(df, settings.paths.eval_testset)
    print(f"Created {len(questions)} questions: {dict(Counter(q['question_type'] for q in questions))}")
    print(f"Test set: {settings.paths.eval_testset}")
