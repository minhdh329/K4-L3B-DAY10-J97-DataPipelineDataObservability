from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
import unittest

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord


def paper(**changes):
    return replace(PaperRecord(
        paper_id="10.1234/a", title="A paper", summary="A summary.",
        authors=["An Nguyen"], categories=["AI"], primary_category="AI",
        published="2026-09-20", updated="2026-09-21",
        abs_url="https://doi.org/10.1234/a", pdf_url="", comment="",
    ), **changes)


class CleaningTests(unittest.TestCase):
    def test_normalization_exact_context_and_raw_unchanged(self):
        records = [paper(
            paper_id=" 10.1234/A ", title="  A\n paper\t ",
            summary=" A\t summary.\n More\u00a0text. ",
            authors=[" An  Nguyen ", "", "Binh\nTran", "An Nguyen"],
            categories=[" AI ", "", "Information\tRetrieval", "AI"],
            published=" 2026-09-20 ",
        )]
        original = deepcopy(records)
        df = build_clean_dataframe(records, datetime(2026, 9, 26, 12, tzinfo=UTC))
        row = df.iloc[0]
        self.assertEqual(row["paper_id"], "10.1234/a")
        self.assertEqual(row["age_days"], 6)
        self.assertEqual(row["authors"], ["An Nguyen", "Binh Tran"])
        self.assertEqual(row["categories"], ["AI", "Information Retrieval"])
        self.assertEqual(row["summary_chars"], len("A summary. More text."))
        self.assertEqual(row["text_for_embedding"],
                         "Title: A paper\nAuthors: An Nguyen, Binh Tran\n"
                         "Published: 2026-09-20\nCategories: AI, Information Retrieval\n"
                         "Summary: A summary. More text.")
        self.assertEqual(records, original)

    def test_first_valid_duplicate_is_kept_before_sorting(self):
        df = build_clean_dataframe([
            paper(title=" "),
            paper(title="First valid"),
            paper(paper_id=" 10.1234/A ", title="Later duplicate", published="2026-09-25"),
            paper(paper_id="10.1234/c", published="2026-09-22"),
            paper(paper_id="10.1234/b", published="2026-09-22"),
        ], datetime(2026, 9, 26))
        self.assertEqual(df["paper_id"].tolist(), ["10.1234/b", "10.1234/c", "10.1234/a"])
        self.assertEqual(df.iloc[2]["title"], "First valid")
        self.assertTrue(df["paper_id"].is_unique)
        self.assertEqual(df.index.tolist(), [0, 1, 2])

    def test_age_timezone_leap_day_and_future(self):
        cases = [
            ("2026-09-20", datetime(2026, 9, 26), 6),
            ("2026-09-20", datetime(2026, 9, 26, 1, tzinfo=timezone(timedelta(hours=7))), 5),
            ("2024-02-28", datetime(2024, 3, 1, tzinfo=UTC), 2),
            ("2026-09-27", datetime(2026, 9, 26, 12, tzinfo=UTC), -1),
        ]
        for published, run_date, expected in cases:
            with self.subTest(published=published, run_date=run_date):
                df = build_clean_dataframe([paper(published=published)], run_date)
                self.assertEqual(df.iloc[0]["age_days"], expected)

    def test_invalid_required_fields_and_empty_optional_metadata(self):
        df = build_clean_dataframe([
            paper(paper_id=""), paper(title="\n"), paper(published=""),
            paper(published="2026-02-30"),
            paper(authors=[], categories=[], summary="", updated="invalid"),
        ], datetime(2026, 9, 26))
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["updated"], "2026-09-20")
        self.assertEqual(row["primary_category"], "")
        self.assertEqual(row["summary_chars"], 0)
        self.assertEqual(row["text_for_embedding"],
                         "Title: A paper\nAuthors: \nPublished: 2026-09-20\nCategories: \nSummary: ")

    def test_empty_dataframe_preserves_schema(self):
        for records in ([], [paper(published="invalid")]):
            df = build_clean_dataframe(records, datetime(2026, 9, 26))
            self.assertTrue(df.empty)
            self.assertIn("text_for_embedding", df.columns)
            self.assertIn("paper_id", df.columns)
            self.assertEqual(str(df["age_days"].dtype), "int64")


if __name__ == "__main__":
    unittest.main()
