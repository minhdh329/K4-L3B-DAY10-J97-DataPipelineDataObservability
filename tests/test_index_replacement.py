from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import chromadb
import pandas as pd

from core.config import load_settings
from retrieval.index import LocalEmbeddingIndex


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[1.0, float(len(text) % 7 + 1), 0.5] for text in texts]


def documents(ids):
    return pd.DataFrame([{
        "paper_id": paper_id, "title": f"Title {paper_id}", "summary": "Research summary",
        "published": "2026-09-20", "authors_joined": "An Nguyen", "categories_joined": "AI",
        "abs_url": "", "pdf_url": "", "text_for_embedding": f"Title: {paper_id}\nSummary: Research summary",
    } for paper_id in ids])


class IndexReplacementTests(unittest.TestCase):
    def setUp(self):
        test_dir = Path(__file__).resolve().parent
        self.temp = tempfile.TemporaryDirectory(dir=test_dir)
        assert Path(self.temp.name).resolve().is_relative_to(test_dir)
        self.addCleanup(self.temp.cleanup)
        self.settings = replace(load_settings(Path(self.temp.name)), baseline_collection_name=f"test-{uuid4().hex}")
        self.client = chromadb.EphemeralClient()
        existing = {collection.name for collection in self.client.list_collections()}

        def cleanup():
            for collection in self.client.list_collections():
                if collection.name not in existing:
                    self.client.delete_collection(collection.name)

        self.addCleanup(cleanup)
        for target, value in (("chromadb.PersistentClient", self.client), ("MiniLMEmbeddings", FakeEmbeddings())):
            patcher = patch(f"retrieval.index.{target}", return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def build(self, ids):
        return LocalEmbeddingIndex.build(documents(ids), self.settings)

    def test_repeated_rebuild_removes_obsolete_and_duplicate_vectors(self):
        self.build(["10.1234/a", "10.1234/a", "10.1234/obsolete"])
        repaired = self.build(["10.1234/a", "10.1234/b"])
        first = repaired.collection.get(include=["metadatas"])
        repaired = self.build(["10.1234/a", "10.1234/b"])
        second = repaired.collection.get(include=["metadatas"])
        self.assertEqual(repaired.collection.count(), 2)
        self.assertEqual(set(first["ids"]), set(second["ids"]))
        self.assertEqual({row["paper_id"] for row in second["metadatas"]}, {"10.1234/a", "10.1234/b"})

    def test_embedding_failure_preserves_live_index_and_manifest(self):
        previous = self.build(["10.1234/original"])
        manifest = self.settings.paths.embeddings_json.read_bytes()
        with patch.object(FakeEmbeddings, "embed_documents", side_effect=RuntimeError("embedding failure")):
            with self.assertRaisesRegex(RuntimeError, "embedding failure"):
                self.build(["10.1234/new"])
        self.assertEqual(previous.collection.count(), 1)
        self.assertEqual(self.settings.paths.embeddings_json.read_bytes(), manifest)

    def test_staging_insert_failure_keeps_live_index(self):
        previous = self.build(["10.1234/original"])
        manifest = self.settings.paths.embeddings_json.read_bytes()
        with patch.object(type(previous.collection), "add", side_effect=RuntimeError("insert failure")):
            with self.assertRaisesRegex(RuntimeError, "insert failure"):
                self.build(["10.1234/new"])
        current = self.client.get_collection(self.settings.baseline_collection_name)
        self.assertEqual(current.get()["ids"], ["10.1234/original::0"])
        self.assertEqual(self.settings.paths.embeddings_json.read_bytes(), manifest)

    def test_failed_publish_restores_previous_collection_name(self):
        previous = self.build(["10.1234/original"])
        original_modify = type(previous.collection).modify

        def fail_publish(collection, *args, **kwargs):
            if collection.name.startswith("staging-") and kwargs.get("name") == self.settings.baseline_collection_name:
                raise RuntimeError("publish failure")
            return original_modify(collection, *args, **kwargs)

        with patch.object(type(previous.collection), "modify", new=fail_publish):
            with self.assertRaisesRegex(RuntimeError, "publish failure"):
                self.build(["10.1234/new"])
        current = self.client.get_collection(self.settings.baseline_collection_name)
        self.assertEqual(current.get()["ids"], ["10.1234/original::0"])


if __name__ == "__main__":
    unittest.main()
