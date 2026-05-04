"""Orchestrating Retriever class.

Composes BM25 + dense (Qdrant) + Reciprocal Rank Fusion + cross-encoder
rerank into a single :meth:`Retriever.search` call. Embedding generation is
delegated via an injected callable so tests can stub it without touching the
OpenAI SDK or the network.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.retrieval.bm25 import BM25Index
from app.retrieval.fusion import reciprocal_rank_fusion
from app.schemas.corpus import CorpusChunk

logger = logging.getLogger(__name__)


class _DenseSearchLike(Protocol):
    def search(
        self, query_embedding: list[float], top_k: int = 20
    ) -> list[tuple[CorpusChunk, float]]: ...


class _RerankerLike(Protocol):
    def rerank(
        self, query: str, candidates: list[tuple[CorpusChunk, float]]
    ) -> list[tuple[CorpusChunk, float]]: ...


EmbedFn = Callable[[str], list[float]]


@dataclass(frozen=True)
class RetrievalResult:
    """The fully ranked output of one retrieval call.

    Attributes:
        query: The original query string.
        chunks: Reranked top chunks with their final scores.
    """

    query: str
    chunks: list[tuple[CorpusChunk, float]]


class Retriever:
    """Hybrid retriever composing BM25 + dense + RRF + reranker.

    Attributes:
        bm25: BM25 sparse index.
        dense: Object exposing ``search(query_embedding, top_k)``.
        reranker: Object exposing ``rerank(query, candidates)``.
        embed: Callable mapping a query string to a dense embedding.
        top_k_per_retriever: How many candidates each retriever yields
            before fusion. Default 20 per spec EPIC-002 5.2.
    """

    def __init__(
        self,
        *,
        bm25: BM25Index,
        dense: _DenseSearchLike,
        reranker: _RerankerLike,
        embed: EmbedFn,
        top_k_per_retriever: int = 20,
    ) -> None:
        self.bm25 = bm25
        self.dense = dense
        self.reranker = reranker
        self.embed = embed
        self.top_k_per_retriever = top_k_per_retriever

    def search(self, query: str) -> RetrievalResult:
        """Run the full hybrid retrieval pipeline for ``query``."""
        sparse = self.bm25.search(query, top_k=self.top_k_per_retriever)
        embedding = self.embed(query)
        dense = self.dense.search(embedding, top_k=self.top_k_per_retriever)
        fused = reciprocal_rank_fusion(sparse, dense, top_n=self.top_k_per_retriever)
        reranked = self.reranker.rerank(query, fused)
        logger.debug(
            "retrieval: sparse=%d dense=%d fused=%d reranked=%d",
            len(sparse),
            len(dense),
            len(fused),
            len(reranked),
        )
        return RetrievalResult(query=query, chunks=reranked)
