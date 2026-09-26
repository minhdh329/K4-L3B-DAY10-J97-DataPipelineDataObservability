from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests

from core.config import load_settings
from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload


def payload(*items):
    return {"status": "ok", "message": {"items": list(items)}}


class ParseTests(unittest.TestCase):
    def test_normalization_and_source_preservation(self):
        source = payload({
            "DOI": " https://doi.org/10.1234/ABC ",
            "title": [" A <i>paper</i> &amp; results "],
            "abstract": "<jats:sec><jats:title>Results</jats:title><jats:p>H<sub>2</sub>O &amp; CO<sub>2</sub>.</jats:p><jats:p>Next\n paragraph.</jats:p></jats:sec>",
            "author": [{"given": " An ", "family": " Nguyen "}, {"name": "Study Group"}, {}],
            "subject": [" AI ", "AI", " Information\nRetrieval ", None],
            "published": {"date-parts": [[2026, 5, 20]]},
            "deposited": {"date-parts": [[2026, 6, 1]]},
            "link": [{"content-type": "text/html", "URL": "https://example.org"},
                     {"content-type": "application/pdf", "URL": "https://example.org/paper.pdf"}],
        })
        original = deepcopy(source)
        record, = parse_crossref_payload(source)
        self.assertEqual(record.paper_id, "10.1234/abc")
        self.assertEqual(record.title, "A paper & results")
        self.assertEqual(record.summary, "Results H2O & CO2. Next paragraph.")
        self.assertEqual(record.authors, ["An Nguyen", "Study Group"])
        self.assertEqual(record.categories, ["AI", "Information Retrieval"])
        self.assertEqual(record.published, "2026-05-20")
        self.assertEqual(record.updated, "2026-06-01")
        self.assertEqual(record.pdf_url, "https://example.org/paper.pdf")
        self.assertEqual(source, original)

    def test_optional_fields_and_invalid_items(self):
        records = parse_crossref_payload(payload(
            None, {}, {"DOI": "bad", "title": ["Title"]}, {"DOI": "10.1234/a"},
            {"DOI": "10.1234/b", "title": ["Title"], "author": None, "subject": None},
        ))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual((record.summary, record.published, record.pdf_url), ("", "", ""))
        self.assertEqual((record.authors, record.categories), ([], []))

    def test_date_precision_and_fallback(self):
        for parts, expected in [([2025], "2025-01-01"), ([2025, 2], "2025-02-01"),
                                ([2024, 2, 29], "2024-02-29"), ([2025, 2, 29], "")]:
            with self.subTest(parts=parts):
                record, = parse_crossref_payload(payload({
                    "DOI": "10.1234/a", "title": ["Title"],
                    "published": {"date-parts": [[2025, 13, 1]]},
                    "issued": {"date-parts": [parts]},
                    "created": {"date-parts": [[2026, 1, 1]]},
                }))
                self.assertEqual(record.published, expected)

    def test_invalid_envelope_is_not_silently_empty(self):
        for source in ({}, {"message": {}}, {"message": {"items": None}}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_crossref_payload(source)
        self.assertEqual(parse_crossref_payload(payload()), [])


class FetchTests(unittest.TestCase):
    def setUp(self):
        test_dir = Path(__file__).resolve().parent
        self.temp = tempfile.TemporaryDirectory(dir=test_dir)
        assert Path(self.temp.name).resolve().is_relative_to(test_dir)
        self.addCleanup(self.temp.cleanup)
        self.settings = load_settings(Path(self.temp.name))

    @patch("ingestion.crossref.requests.Session")
    def test_exact_response_bytes_records_roundtrip_and_request(self, session_type):
        body = b'{ "status":"ok", "message":{"items":[{"DOI":"10.1234/a","title":["Caf\\u00e9"],"abstract":"<jats:p>Text</jats:p>"}]}}\r\n'
        response = requests.Response()
        response.status_code = 200
        response._content = body
        session = session_type.return_value.__enter__.return_value
        session.get.return_value = response

        records = fetch_source_records(self.settings)

        self.assertEqual(self.settings.paths.raw_api_response.read_bytes(), body)
        self.assertEqual(load_raw_records(self.settings.paths.raw_records_json), records)
        self.assertEqual(records[0].summary, "Text")
        args, kwargs = session.get.call_args
        self.assertEqual(args, ("https://api.crossref.org/works",))
        self.assertEqual(kwargs["params"], {"rows": self.settings.max_results,
                                          "query": self.settings.source_query,
                                          "filter": self.settings.source_filter})
        retry = session.mount.call_args.args[1].max_retries
        for status in (429, 503):
            self.assertTrue(retry.is_retry("GET", status))
        self.assertFalse(retry.is_retry("GET", 400))
        self.assertEqual(retry.total, 3)
        self.assertTrue(retry.respect_retry_after_header)

    @patch("ingestion.crossref.requests.Session")
    def test_failed_response_preserves_existing_artifacts(self, session_type):
        for path in (self.settings.paths.raw_api_response, self.settings.paths.raw_records_json):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"original")
        for status, body, error in [(503, b"unavailable", requests.HTTPError),
                                    (200, b"not json", requests.exceptions.JSONDecodeError),
                                    (200, b"{}", ValueError)]:
            with self.subTest(status=status, body=body):
                response = requests.Response()
                response.status_code = status
                response._content = body
                session_type.return_value.__enter__.return_value.get.return_value = response
                with self.assertRaises(error):
                    fetch_source_records(self.settings)
                self.assertEqual(self.settings.paths.raw_api_response.read_bytes(), b"original")
                self.assertEqual(self.settings.paths.raw_records_json.read_bytes(), b"original")

    def test_invalid_result_limit(self):
        for count in (0, -1, 1001):
            with self.subTest(count=count), self.assertRaises(ValueError):
                fetch_source_records(replace(self.settings, max_results=count))


if __name__ == "__main__":
    unittest.main()
