"""Cross-encoder reranker.

Wraps ``BAAI/bge-reranker-v2-m3`` (or any cross-encoder loadable via
``sentence-transformers``) behind a narrow interface so unit tests can
substitute a deterministic stub. The real model is heavy (~600 MB) so it is
loaded lazily on first use; tests should always inject a stub.
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.schemas.corpus import CorpusChunk

logger = logging.getLogger(__name__)


class _CrossEncoderLike(Protocol):
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]: ...


class CrossEncoderReranker:
    """Cross-encoder reranker over candidate chunks.

    Attributes:
        model_name: Hugging Face model identifier.
        top_n: Number of chunks to return after reranking. Default 5
            (spec EPIC-002 5.2 reranks top-20 fused candidates to top-5).
    """

    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        top_n: int = 5,
        encoder: _CrossEncoderLike | None = None,
    ) -> None:
        self.model_name = model_name
        self.top_n = top_n
        self._encoder: _CrossEncoderLike | None = encoder

    def _load(self) -> _CrossEncoderLike:
        if self._encoder is not None:
            return self._encoder
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers not available; install dev extras (uv sync --extra dev)"
            ) from exc
        logger.info("Loading cross-encoder model %s", self.model_name)
        encoder: _CrossEncoderLike = CrossEncoder(self.model_name)
        self._encoder = encoder
        return encoder

    def rerank(
        self,
        query: str,
        candidates: list[tuple[CorpusChunk, float]],
    ) -> list[tuple[CorpusChunk, float]]:
        """Rerank candidates by cross-encoder score against ``query``.

        Args:
            query: The retrieval query.
            candidates: Candidate ``(chunk, fused_score)`` list, typically
                produced by :func:`app.retrieval.fusion.reciprocal_rank_fusion`.

        Returns:
            The top-``self.top_n`` candidates sorted by cross-encoder score
            (descending).
        """
        if not candidates:
            return []
        encoder = self._load()
        pairs = [(query, chunk.text) for chunk, _ in candidates]
        scores = encoder.predict(pairs)
        ranked = sorted(
            zip(candidates, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [(chunk_score[0], float(score)) for chunk_score, score in ranked[: self.top_n]]


class RerankerStub:
    """Deterministic reranker stub used in unit tests.

    Sorts candidates by descending fused score and returns the top-n. No
    model load, no inference. Useful when you want to exercise the
    retrieval pipeline without paying for the cross-encoder weights.
    """

    def __init__(self, top_n: int = 5) -> None:
        self.top_n = top_n

    def rerank(
        self,
        query: str,
        candidates: list[tuple[CorpusChunk, float]],
    ) -> list[tuple[CorpusChunk, float]]:
        """Sort by descending fused score and truncate to ``top_n``."""
        del query
        ranked = sorted(candidates, key=lambda pair: pair[1], reverse=True)
        return ranked[: self.top_n]
