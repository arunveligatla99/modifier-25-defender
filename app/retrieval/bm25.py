"""BM25 sparse retrieval index.

A thin wrapper over ``rank_bm25`` that maps query results back to the
:class:`CorpusChunk` instances they came from. Tokenization is a simple
lowercase whitespace split for v1; the spec does not require linguistic
preprocessing and adding it would change retrieval scores in ways that
require re-tuning AC-002-3.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.schemas.corpus import CorpusChunk

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase + alphanumeric token split."""
    return _TOKEN_RE.findall(text.lower())


@dataclass
class BM25Index:
    """In-memory BM25 index over a list of :class:`CorpusChunk`.

    Attributes:
        chunks: The indexed chunks, in the order they were provided.
    """

    chunks: list[CorpusChunk]

    def __post_init__(self) -> None:
        """Tokenize all chunks and build the BM25 engine."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:  # pragma: no cover - rank_bm25 is in deps
            raise RuntimeError(
                "rank_bm25 not available; install dev extras (uv sync --extra dev)"
            ) from exc
        self._tokenized: list[list[str]] = [tokenize(c.text) for c in self.chunks]
        self._engine = BM25Okapi(self._tokenized) if self._tokenized else None

    def search(self, query: str, top_k: int = 20) -> list[tuple[CorpusChunk, float]]:
        """Return ``top_k`` chunks ranked by BM25 score for ``query``."""
        if self._engine is None or not self.chunks:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = self._engine.get_scores(q_tokens)
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)[:top_k]
        return [(self.chunks[i], float(score)) for i, score in ranked]
