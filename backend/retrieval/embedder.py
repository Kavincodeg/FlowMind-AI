"""
FlowMind AI - Embedder (Phase 1)

Wraps sentence-transformers all-MiniLM-L6-v2 (384 dims, local, no API key).
Provides batched embedding for both single strings and lists of Chunk objects.
"""
from __future__ import annotations

import logging
import os
from typing import List, Union

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.retrieval.models import Chunk

logger = logging.getLogger(__name__)

# Default model — swap here without touching any other code
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
DEFAULT_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))


class Embedder:
    """
    Singleton-style embedder.  Loads the model once and reuses it.

    Usage:
        embedder = Embedder()
        vectors = embedder.embed_texts(["hello world", "another sentence"])
        chunks  = embedder.embed_chunks(chunk_list)
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        logger.info("Loading embedding model: %s", model_name)
        self._model = SentenceTransformer(model_name, device=device)
        self.embedding_dim: int = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Model loaded — dim=%d, device=%s", self.embedding_dim, device or "auto"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of plain strings.

        Returns:
            np.ndarray of shape (len(texts), embedding_dim), dtype float32
        """
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        logger.debug("Embedding %d texts in batches of %d", len(texts), self.batch_size)
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,   # unit-norm so cosine sim == dot product
        )
        return vectors.astype(np.float32)

    def embed_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Embed a list of Chunk objects in place.

        Sets chunk.embedding on each chunk and returns the same list.
        """
        if not chunks:
            return chunks

        texts = [c.content for c in chunks]
        vectors = self.embed_texts(texts)

        for chunk, vec in zip(chunks, vectors):
            chunk.embedding = vec.tolist()

        logger.info("Embedded %d chunks", len(chunks))
        return chunks

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string — returns shape (embedding_dim,)."""
        return self.embed_texts([query])[0]


# Module-level singleton (lazy-loaded on first use)
_default_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Return the module-level default Embedder, creating it if needed."""
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = Embedder()
    return _default_embedder
