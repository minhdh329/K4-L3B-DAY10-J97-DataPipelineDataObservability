from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_json
from evaluation.metrics import EvaluationBundle
from ingestion.crossref import PaperRecord
from pipelines.corruption_flow import repair_from_raw_snapshot, run_corruption_flow_pipeline


class CorruptionFlowTests(unittest.TestCase):
    def setUp(self):
        test_dir = Path(__file__).resolve().parent
        self.temp = tempfile.TemporaryDirectory(dir=test_dir)
        assert Path(self.temp.name).resolve().is_relative_to(test_dir)
        self.addCleanup(self.temp.cleanup)
        self.settings = load_settings(Path(self.temp.name))
        self.run_date = datetime(2026, 9, 26, tzinfo=UTC)
        self.records = [PaperRecord(
            paper_id=f"10.1234/{i}", title=f"Research paper number {i}",
            summary="A long research summary with evidence for the first sentence. Further details.",
            authors=["An Nguyen"], categories=["AI"], primary_category="AI",
            published=f"2026-09-{i + 1:02d}", updated="2026-09-20",
            abs_url="", pdf_url="", comment="",
        ) for i in range(8)]
        write_json(self.settings.paths.raw_records_json, [asdict(record) for record in self.records])
        self.builds = []
        self.evaluations = []
        self.fail_corrupted_evaluation = False
        self.fail_repair_gate = False
        self.patch("now_utc", return_value=self.run_date)
        self.gate = self.patch("run_data_quality_checks", side_effect=self.check_quality)
        self.build = self.patch("LocalEmbeddingIndex.build", side_effect=self.build_index)
        self.patch("evaluate_pipeline", side_effect=self.evaluate)

    def patch(self, name, **kwargs):
        patcher = patch(f"pipelines.corruption_flow.{name}", **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def check_quality(self, df, settings, stage):
        success = stage != "corrupted" and not (stage == "repaired" and self.fail_repair_gate)
        return {"success": success, "statistics": {"successful_expectations": 7 if success else 5,
                                                   "evaluated_expectations": 7}}

    def build_index(self, df, settings, embeddings_output_path):
        self.builds.append((embeddings_output_path, df.copy(deep=True)))
        return SimpleNamespace(documents=df.to_dict(orient="records"))

    def evaluate(self, settings, index, test_set_path, metrics_output_path, answers_output_path):
        questions = read_json(test_set_path)
        self.evaluations.append(questions)
        corrupted = metrics_output_path == settings.paths.corrupted_metrics
        if corrupted and self.fail_corrupted_evaluation:
            raise RuntimeError("simulated evaluation failure")
        summary = {"samples": len(questions), "retrieval_hit_rate": 0.7 if corrupted else 1.0,
                   "mean_token_f1": 0.4 if corrupted else 0.8}
        write_json(metrics_output_path, summary)
        write_json(answers_output_path, [])
        return EvaluationBundle(summary, [])

    def test_three_states_and_working_corpus_are_restored(self):
        raw_before = self.settings.paths.raw_records_json.read_bytes()
        result = run_corruption_flow_pipeline(self.settings)
        self.assertTrue(result["success"])
        self.assertEqual(result["baseline"], result["repaired"])
        self.assertLess(result["corrupted"]["mean_token_f1"], result["baseline"]["mean_token_f1"])
        self.assertEqual(self.evaluations[0], self.evaluations[1])
        self.assertEqual(self.evaluations[0], self.evaluations[2])
        self.assertEqual(self.settings.paths.raw_records_json.read_bytes(), raw_before)
        self.assertEqual(read_json(self.settings.paths.clean_json), read_json(self.settings.paths.repaired_clean_json))
        self.assertNotEqual(read_json(self.settings.paths.clean_json), read_json(self.settings.paths.corrupted_clean_json))
        working_builds = [df for path, df in self.builds if path == self.settings.paths.embeddings_json]
        self.assertEqual(len(working_builds), 3)
        self.assertFalse(working_builds[1].paper_id.is_unique)
        pd.testing.assert_frame_equal(working_builds[0], working_builds[2])
        report = self.settings.paths.comparison_report.read_text(encoding="utf-8")
        self.assertIn("| Metric | Baseline | Corrupted | Repaired |", report)
        self.assertIn("| Mean Token F1 | 0.8000 | 0.4000 | 0.8000 |", report)

    def test_repair_is_idempotent_and_ignores_dirty_clean_files(self):
        write_json(self.settings.paths.clean_json, [{"broken": "data"}])
        first = repair_from_raw_snapshot(self.settings, self.run_date)
        first_bytes = self.settings.paths.clean_json.read_bytes()
        second = repair_from_raw_snapshot(self.settings, self.run_date)
        pd.testing.assert_frame_equal(first.dataframe, second.dataframe)
        self.assertEqual(self.settings.paths.clean_json.read_bytes(), first_bytes)
        self.assertTrue(second.dataframe.paper_id.is_unique)
        self.assertEqual(len(second.dataframe), 8)

    def test_repair_runs_even_when_corrupted_evaluation_raises(self):
        self.fail_corrupted_evaluation = True
        with self.assertRaisesRegex(RuntimeError, "simulated evaluation failure"):
            run_corruption_flow_pipeline(self.settings)
        self.assertEqual(read_json(self.settings.paths.clean_json), read_json(self.settings.paths.repaired_clean_json))
        self.assertEqual(self.builds[-1][0], self.settings.paths.embeddings_json)
        self.assertTrue(self.builds[-1][1].paper_id.is_unique)
        self.assertFalse(self.settings.paths.comparison_report.exists())

    def test_failed_repair_gate_does_not_replace_working_data(self):
        self.fail_repair_gate = True
        write_json(self.settings.paths.clean_json, [{"existing": "working copy"}])
        original = self.settings.paths.clean_json.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "repair quality gate"):
            repair_from_raw_snapshot(self.settings, self.run_date)
        self.build.assert_not_called()
        self.assertEqual(self.settings.paths.clean_json.read_bytes(), original)

    def test_missing_raw_snapshot_stops_without_index_changes(self):
        self.settings.paths.raw_records_json.unlink()
        with self.assertRaises(FileNotFoundError):
            repair_from_raw_snapshot(self.settings, self.run_date)
        self.build.assert_not_called()

    def test_existing_ground_truth_is_not_regenerated(self):
        write_json(self.settings.paths.eval_testset, [{"invalid": "ground truth"}])
        before = self.settings.paths.eval_testset.read_bytes()
        with self.assertRaisesRegex(ValueError, "Ground Truth"):
            run_corruption_flow_pipeline(replace(self.settings, refresh_test_set=True, refresh_source=True))
        self.build.assert_not_called()
        self.assertEqual(self.settings.paths.eval_testset.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
