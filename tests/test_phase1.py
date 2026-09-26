from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from core.config import load_settings
from core.utils import read_json, write_json
from evaluation.metrics import EvaluationBundle, _judge_answer, _token_f1
from ingestion.crossref import PaperRecord
from pipelines.phase1 import _ingest, run_phase1_pipeline


class Phase1Tests(unittest.TestCase):
    def setUp(self):
        test_dir = Path(__file__).resolve().parent
        self.temp = tempfile.TemporaryDirectory(dir=test_dir)
        assert Path(self.temp.name).resolve().is_relative_to(test_dir)
        self.addCleanup(self.temp.cleanup)
        self.settings = replace(load_settings(Path(self.temp.name)), refresh_source=False, refresh_test_set=False)
        self.records = [PaperRecord(
            paper_id=f"10.1234/{i}", title=f"Paper {i}",
            summary="This first sentence contains a valid research summary. More details follow.",
            authors=["An Nguyen"], categories=["AI"], primary_category="AI",
            published="2026-09-20", updated="2026-09-20", abs_url="", pdf_url="", comment="",
        ) for i in range(5)]
        write_json(self.settings.paths.raw_records_json, [asdict(record) for record in self.records])
        self.events = []
        self.quality = {"success": True, "gx_success": True, "missing_columns": [],
                        "statistics": {"successful_expectations": 7, "evaluated_expectations": 7}}
        self.metrics = {"samples": 10, "retrieval_hit_rate": 0.9, "mean_token_f1": 0.8}
        self.gate = self.patch("run_data_quality_checks", side_effect=self.check_quality)
        self.index = self.patch("LocalEmbeddingIndex.build", side_effect=self.build_index)
        self.evaluate = self.patch("evaluate_pipeline", side_effect=self.evaluate_baseline)
        self.fetch = self.patch("fetch_source_records", return_value=self.records)
        self.patch("now_utc", return_value=datetime(2026, 9, 26, tzinfo=UTC))

    def patch(self, name, **kwargs):
        patcher = patch(f"pipelines.phase1.{name}", **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def check_quality(self, *args, **kwargs):
        self.events.append("quality")
        return self.quality

    def build_index(self, *args, **kwargs):
        self.events.append("index")
        return Mock()

    def evaluate_baseline(self, **kwargs):
        self.events.append("evaluate")
        write_json(kwargs["metrics_output_path"], self.metrics)
        write_json(kwargs["answers_output_path"], [])
        return EvaluationBundle(summary=self.metrics, answers=[])

    def test_complete_pipeline_and_snapshot_reuse(self):
        original_raw = self.settings.paths.raw_records_json.read_bytes()
        result = run_phase1_pipeline(self.settings)
        self.assertTrue(result["success"])
        self.assertEqual(self.events, ["quality", "index", "evaluate"])
        self.assertEqual(result["source_summary"]["source_mode"], "raw_records_snapshot")
        self.assertEqual(result["source_summary"]["testset_mode"], "generated")
        self.assertEqual(len(read_json(self.settings.paths.eval_testset)), 10)
        self.assertEqual(read_json(self.settings.paths.baseline_metrics), self.metrics)
        report = self.settings.paths.baseline_report.read_text(encoding="utf-8")
        self.assertIn("90.00%", report)
        self.assertIn("0.8000", report)
        self.assertIn("COMPLETED", report)
        self.assertEqual(self.settings.paths.raw_records_json.read_bytes(), original_raw)
        original_testset = self.settings.paths.eval_testset.read_bytes()
        result = run_phase1_pipeline(self.settings)
        self.assertEqual(result["source_summary"]["testset_mode"], "snapshot")
        self.assertEqual(self.settings.paths.eval_testset.read_bytes(), original_testset)
        self.fetch.assert_not_called()

    def test_failed_quality_gate_blocks_indexing_and_evaluation(self):
        self.quality["success"] = False
        with self.assertRaisesRegex(RuntimeError, "indexing blocked"):
            run_phase1_pipeline(self.settings)
        self.index.assert_not_called()
        self.evaluate.assert_not_called()
        self.assertFalse(self.settings.paths.eval_testset.exists())
        self.assertFalse(self.settings.paths.baseline_metrics.exists())
        self.assertIn("BLOCKED", self.settings.paths.baseline_report.read_text())

    def test_refresh_fetches_source_and_rebuilds_testset(self):
        result = run_phase1_pipeline(replace(self.settings, refresh_source=True))
        self.fetch.assert_called_once()
        self.assertEqual(result["source_summary"]["source_mode"], "crossref_api")
        self.assertEqual(result["source_summary"]["testset_mode"], "generated")

    def test_network_failure_falls_back_to_snapshot(self):
        self.fetch.side_effect = requests.Timeout("offline")
        result = run_phase1_pipeline(replace(self.settings, refresh_source=True))
        self.assertTrue(result["success"])
        self.assertEqual(result["source_summary"]["source_mode"], "raw_records_snapshot")

    def test_network_failure_without_cache_raises(self):
        self.settings.paths.raw_records_json.unlink()
        self.fetch.side_effect = requests.Timeout("offline")
        with self.assertRaises(requests.Timeout):
            run_phase1_pipeline(self.settings)
        self.index.assert_not_called()

    def test_api_snapshot_can_restore_record_snapshot(self):
        self.settings.paths.raw_records_json.unlink()
        write_json(self.settings.paths.raw_api_response, {"message": {"items": [
            {"DOI": "10.1234/a", "title": ["Title"], "abstract": "<jats:p>Text</jats:p>"}
        ]}})
        records, source_mode = _ingest(self.settings)
        self.assertEqual(source_mode, "raw_response_snapshot")
        self.assertEqual(records[0].summary, "Text")
        self.assertTrue(self.settings.paths.raw_records_json.exists())
        self.fetch.assert_not_called()

    def test_invalid_or_stale_testset_is_regenerated(self):
        self.settings.paths.eval_testset.parent.mkdir(parents=True, exist_ok=True)
        self.settings.paths.eval_testset.write_text("invalid JSON")
        result = run_phase1_pipeline(self.settings)
        self.assertEqual(result["source_summary"]["testset_mode"], "generated")
        testset = read_json(self.settings.paths.eval_testset)
        testset[0]["ground_truth_doc_ids"] = ["10.1234/removed"]
        write_json(self.settings.paths.eval_testset, testset)
        result = run_phase1_pipeline(self.settings)
        self.assertEqual(result["source_summary"]["testset_mode"], "generated")
        result = run_phase1_pipeline(replace(self.settings, refresh_test_set=True))
        self.assertEqual(result["source_summary"]["testset_mode"], "generated")


class MetricTests(unittest.TestCase):
    def test_token_f1_counts_repeated_tokens(self):
        self.assertAlmostEqual(_token_f1("a a b", "a b b"), 2 / 3)
        self.assertEqual(_token_f1(" A  B ", "a b"), 1.0)
        self.assertEqual(_token_f1("", "anything"), 0.0)
        self.assertEqual(_token_f1("a", "b"), 0.0)

    @patch.dict("os.environ", {"RUN_LLM_JUDGE": "false"})
    @patch("evaluation.metrics.build_llm")
    def test_default_baseline_needs_no_llm_calls(self, build_llm):
        result = _judge_answer(load_settings(), "question", "a b", "a b")
        self.assertEqual(result.score, 5)
        self.assertTrue(result.correct)
        build_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
