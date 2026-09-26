from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=4)
def _load_model(model_name: str) -> SentenceTransformer:
    """Load a previously downloaded model without a network metadata check.

    The lab must run from its local artifacts after the initial setup, including
    during a Crossref fallback or when a classroom network is unavailable.
    """
    return SentenceTransformer(model_name, local_files_only=True)


class MiniLMEmbeddings(Embeddings):
    def __init__(self, model_name: str):
        self.model = _load_model(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Keep peak memory small for classroom machines; Chroma receives the
        # same normalized vectors regardless of this batching choice.
        embeddings = self.model.encode(texts, batch_size=1, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode([text], normalize_embeddings=True)
        return embedding[0].tolist()
