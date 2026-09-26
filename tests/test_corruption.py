from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import NOISE, corrupt_clean_dataframe
from ingestion.crossref import PaperRecord


def clean_data(count=24):
    records = [PaperRecord(
        paper_id=f"10.1234/{i:02d}", title=f"Research paper number {i}",
        summary=f"This is a sufficiently long summary for research paper {i}.",
        authors=["An Nguyen"], categories=["AI"], primary_category="AI",
        published=f"2026-09-{i + 1:02d}", updated="2026-09-25",
        abs_url="", pdf_url="", comment="",
    ) for i in range(count)]
    return build_clean_dataframe(records, datetime(2026, 9, 26, tzinfo=UTC))


class CorruptionTests(unittest.TestCase):
    def setUp(self):
        writer = patch("ingestion.corruption.write_json")
        self.write = writer.start()
        self.addCleanup(writer.stop)

    def test_all_six_faults_and_consistent_embedding_fields(self):
        original = clean_data()
        corrupted = corrupt_clean_dataframe(original, "corruption_log.json")
        path, report = self.write.call_args.args
        self.assertEqual(path, Path("corruption_log.json"))
        self.assertEqual(report["counts"], {
            "drop_latest_records": 5, "blank_summary": 2, "inject_noise": 2,
            "truncate_title": 2, "stale_date": 6, "duplicate_rows": 2,
        })
        self.assertEqual(len(corrupted), 21)
        self.assertEqual(corrupted.paper_id.duplicated().sum(), 2)
        self.assertTrue(set(original.iloc[:5].paper_id).isdisjoint(corrupted.paper_id))
        self.assertGreater((corrupted.age_days > 180).mean(), 0.25)
        for event in report["events"]:
            before, after = event["before"], event["after"]
            if event["operation"] == "blank_summary":
                self.assertEqual(after["summary"], "")
            elif event["operation"] == "inject_noise":
                self.assertEqual(after["summary"], NOISE + before["summary"])
            elif event["operation"] == "truncate_title":
                self.assertLess(len(after["title"]), 8)
            elif event["operation"] == "stale_date":
                self.assertEqual((pd.Timestamp(before["published"]) - pd.Timestamp(after["published"])).days, 365)
                self.assertEqual(after["age_days"], before["age_days"] + 365)
            elif event["operation"] == "duplicate_rows":
                self.assertEqual(before, after)
        for row in corrupted.to_dict(orient="records"):
            self.assertEqual(row["summary_chars"], len(row["summary"]))
            self.assertEqual(row["text_for_embedding"],
                             f"Title: {row['title']}\nAuthors: {row['authors_joined']}\n"
                             f"Published: {row['published']}\nCategories: {row['categories_joined']}\n"
                             f"Summary: {row['summary']}")

    def test_log_can_replay_every_row_change_even_with_overlapping_faults(self):
        original = clean_data(5)
        corrupted = corrupt_clean_dataframe(original, "log.json")
        events = self.write.call_args.args[1]["events"]
        state = {i: deepcopy(row) for i, row in enumerate(original.to_dict(orient="records"))}
        output = {}
        for event in events:
            source = event["source_position"]
            self.assertEqual(event["before"], state[source])
            if event["operation"] == "drop_latest_records":
                del state[source]
            elif event["operation"] == "duplicate_rows":
                output[event["output_position"]] = event["after"]
            else:
                state[source] = event["after"]
                output[event["output_position"]] = event["after"]
        self.assertEqual([output[i] for i in range(len(corrupted))], corrupted.to_dict(orient="records"))
        self.assertEqual(len({e["event_id"] for e in events}), len(events))

    def test_deterministic_and_input_is_deeply_preserved(self):
        original = clean_data()
        original.index = ["same-index"] * len(original)
        before = deepcopy(original.to_dict(orient="records"))
        first = corrupt_clean_dataframe(original, "log.json")
        first_log = deepcopy(self.write.call_args.args[1])
        second = corrupt_clean_dataframe(original, "log.json")
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first_log, self.write.call_args.args[1])
        first.at[0, "authors"].append("Changed author")
        self.assertEqual(original.to_dict(orient="records"), before)
        self.assertEqual(original.index.tolist(), ["same-index"] * len(original))

    def test_latest_selection_uses_dates_not_input_order(self):
        original = clean_data().sample(frac=1, random_state=42)
        corrupted = corrupt_clean_dataframe(original, "log.json")
        latest = set(original.sort_values("published", ascending=False).iloc[:5].paper_id)
        self.assertTrue(latest.isdisjoint(corrupted.paper_id))
        self.assertEqual(corrupted.index.tolist(), list(range(len(corrupted))))

    def test_invalid_input_does_not_write_log(self):
        duplicate = clean_data(5)
        duplicate.loc[0, "paper_id"] = duplicate.loc[1, "paper_id"]
        invalid_date = clean_data(5)
        invalid_date.loc[0, "published"] = "invalid"
        for frame in (clean_data(4), clean_data().drop(columns="summary"), duplicate, invalid_date):
            with self.subTest(rows=len(frame)), self.assertRaises(ValueError):
                corrupt_clean_dataframe(frame, "existing_log.json")
        self.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
