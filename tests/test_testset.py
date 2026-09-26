from collections import Counter
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from evaluation.testset import MISSING_CATEGORIES, build_test_set


def papers(count=12):
    return pd.DataFrame([{
        "paper_id": f"10.1234/{i:02d}",
        "title": f"Paper {i}",
        "summary": f"First sentence for paper {i}. Second sentence.",
        "authors": [f"Author {i}", "Another Author"],
        "categories": ["AI", "Information Retrieval"],
        "published": "2026-05-20",
    } for i in range(count)])


class TestSetTests(unittest.TestCase):
    def setUp(self):
        writer = patch("evaluation.testset.write_json")
        self.write = writer.start()
        self.addCleanup(writer.stop)

    def test_exact_schema_distribution_ground_truth_and_no_mutation(self):
        df = papers()
        before = df.copy(deep=True)
        result = build_test_set(df, "test_set.json")
        self.assertEqual(len(result), 10)
        self.assertEqual(Counter(q["question_type"] for q in result),
                         {"summary": 3, "authors": 3, "date": 2, "categories": 2})
        self.assertEqual([q["id"] for q in result], [f"eval_{i:03d}" for i in range(1, 11)])
        self.assertEqual(len({q["ground_truth_doc_ids"][0] for q in result}), 10)
        source = df.set_index("paper_id")
        for question in result:
            self.assertEqual(set(question), {"id", "question_type", "question", "ground_truth", "ground_truth_doc_ids"})
            row = source.loc[question["ground_truth_doc_ids"][0]]
            self.assertIn(row["title"], question["question"])
            expected = {
                "summary": row["summary"].split(". ")[0] + ".",
                "authors": ", ".join(row["authors"]),
                "date": row["published"],
                "categories": ", ".join(row["categories"]),
            }
            self.assertEqual(question["ground_truth"], expected[question["question_type"]])
        pd.testing.assert_frame_equal(df, before)
        self.write.assert_called_once_with(Path("test_set.json"), result)

    def test_stable_when_input_is_shuffled(self):
        df = papers()
        self.assertEqual(build_test_set(df, "a.json"),
                         build_test_set(df.sample(frac=1, random_state=7), "b.json"))

    def test_three_papers_allow_ten_distinct_type_document_pairs(self):
        result = build_test_set(pd.concat([papers(3), papers(3)]), "test.json")
        self.assertEqual(len({(q["question_type"], q["ground_truth_doc_ids"][0]) for q in result}), 10)

    def test_missing_categories_are_explicit_not_invented(self):
        df = papers()
        df["categories"] = [[] for _ in range(len(df))]
        result = build_test_set(df, "test.json")
        category_questions = [q for q in result if q["question_type"] == "categories"]
        self.assertEqual(len(category_questions), 2)
        self.assertTrue(all(q["ground_truth"] == MISSING_CATEGORIES for q in category_questions))

    def test_known_categories_are_preferred(self):
        df = papers()
        df["categories"] = [[] for _ in range(len(df))]
        df.at[0, "categories"] = ["AI"]
        df.at[1, "categories"] = ["AI"]
        result = build_test_set(df, "test.json")
        self.assertEqual([q["ground_truth"] for q in result if q["question_type"] == "categories"], ["AI", "AI"])

    def test_joined_columns_and_unicode_are_preserved(self):
        df = papers(3).drop(columns=["authors", "categories"])
        df["authors_joined"] = " Nguyễn\tVăn A, Trần B "
        df["categories_joined"] = " Trí tuệ\nnhân tạo "
        result = build_test_set(df, "test.json")
        self.assertTrue(all(q["ground_truth"] == "Nguyễn Văn A, Trần B" for q in result if q["question_type"] == "authors"))
        self.assertTrue(all(q["ground_truth"] == "Trí tuệ nhân tạo" for q in result if q["question_type"] == "categories"))

    def test_incomplete_input_raises_before_writing(self):
        bad_summary = papers(3)
        bad_summary.loc[0, "summary"] = None
        bad_dates = papers(3)
        bad_dates["published"] = "invalid"
        for df in (papers(0), papers(2), papers().drop(columns="title"), bad_summary, bad_dates):
            with self.subTest(shape=df.shape), self.assertRaises(ValueError):
                build_test_set(df, "existing.json")
        self.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
