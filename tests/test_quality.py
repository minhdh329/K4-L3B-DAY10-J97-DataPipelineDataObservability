from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import pandas as pd

from core.config import load_settings
from observability.quality import build_freshness_report, evaluate_freshness_sla, run_data_quality_checks


def papers(count=8):
    return pd.DataFrame({
        "paper_id": [f"10.1234/{i}" for i in range(count)],
        "title": ["A valid title"] * count,
        "text_for_embedding": ["Title: A valid title\nSummary: " + "s" * 30] * count,
        "summary": ["s" * 30] * count,
        "age_days": [180] * count,
        "published": ["2026-03-30"] * count,
    })


class FreshnessTests(unittest.TestCase):
    def test_strict_boundaries(self):
        df = papers()
        df.loc[:1, "age_days"] = 181
        report = evaluate_freshness_sla(df)
        self.assertEqual(report["stale_rows"], 2)
        self.assertEqual(report["stale_ratio"], 0.25)
        self.assertTrue(report["is_fresh"])
        df.loc[2, "age_days"] = 181
        self.assertFalse(evaluate_freshness_sla(df)["is_fresh"])

    def test_unknown_ages_and_empty_data_fail(self):
        for age in (None, "invalid", float("inf"), float("-inf")):
            df = papers().astype({"age_days": object})
            df.loc[0, "age_days"] = age
            with self.subTest(age=age):
                report = evaluate_freshness_sla(df)
                self.assertFalse(report["is_fresh"])
                self.assertEqual(report["invalid_age_rows"], 1)
        self.assertFalse(evaluate_freshness_sla(papers(0))["is_fresh"])
        self.assertFalse(evaluate_freshness_sla(papers().drop(columns="age_days"))["is_fresh"])

    @patch("observability.quality.write_json")
    def test_freshness_report_uses_same_sla(self, write):
        df = papers()
        df.loc[0, "published"] = "2026-04-10"
        settings = load_settings()
        report = build_freshness_report(df, settings, settings.paths.freshness_report)
        self.assertEqual(report["oldest_published"], "2026-03-30")
        self.assertEqual(report["latest_published"], "2026-04-10")
        self.assertTrue(report["is_fresh"])
        write.assert_called_once_with(settings.paths.freshness_report, report)


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings()
        writer = patch("observability.quality.write_json")
        self.write = writer.start()
        self.addCleanup(writer.stop)

    def check(self, df):
        return run_data_quality_checks(df, self.settings, stage="test")

    def test_real_gx_success_report_and_no_input_mutation(self):
        df = papers()
        before = deepcopy(df)
        report = self.check(df)
        self.assertIs(report["success"], True)
        self.assertEqual(report["statistics"]["evaluated_expectations"], 7)
        kinds = {item["expectation_config"]["type"] for item in report["results"]}
        self.assertEqual(kinds, {
            "expect_table_row_count_to_be_between", "expect_column_values_to_not_be_null",
            "expect_column_values_to_be_unique", "expect_column_value_lengths_to_be_between",
        })
        pd.testing.assert_frame_equal(df, before)
        self.assertEqual(json.loads(json.dumps(report))["success"], True)
        self.write.assert_called_once_with(self.settings.paths.quality_dir / "test_quality_report.json", report)

    def test_row_count_inclusive_bounds(self):
        for count, expected in ((4, False), (5, True), (5000, True), (5001, False), (0, False)):
            with self.subTest(count=count):
                self.assertIs(self.check(papers(count))["success"], expected)

    def test_critical_null_or_blank_values_fail(self):
        for column in ("paper_id", "title", "text_for_embedding", "summary"):
            for value in (None, " \t\n"):
                with self.subTest(column=column, value=value):
                    df = papers()
                    df.loc[0, column] = value
                    before = df.copy(deep=True)
                    self.assertIs(self.check(df)["gx_success"], False)
                    pd.testing.assert_frame_equal(df, before)

    def test_duplicates_and_short_summary_fail(self):
        for column, value in (("paper_id", "10.1234/1"), ("summary", "s" * 29)):
            with self.subTest(column=column):
                df = papers()
                df.loc[0, column] = value
                report = self.check(df)
                self.assertFalse(report["success"])
                self.assertTrue(report["is_fresh"])

    def test_freshness_blocks_gate_even_when_gx_passes(self):
        df = papers()
        df.loc[:2, "age_days"] = 181
        report = self.check(df)
        self.assertTrue(report["gx_success"])
        self.assertFalse(report["success"])
        self.assertFalse(report["is_fresh"])

    def test_missing_columns_return_failure(self):
        report = self.check(papers().drop(columns="title"))
        self.assertFalse(report["success"])
        self.assertEqual(report["missing_columns"], ["title"])
        report = self.check(papers().drop(columns="age_days"))
        self.assertFalse(report["success"])
        self.assertEqual(report["freshness"]["invalid_age_rows"], 8)


if __name__ == "__main__":
    unittest.main()
