"""Unit tests for the orchestrating Retriever."""

from __future__ import annotations

from app.retrieval.bm25 import BM25Index
from app.retrieval.reranker import RerankerStub
from app.retrieval.retriever import Retriever
from app.schemas.corpus import CorpusChunk


def _chunk(text: str, chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        text=text,
        source_document="x",
        authority_tier="OTHER",
    )


class FakeDense:
    """Stand-in dense index with a fixed return list."""

    def __init__(self, results: list[tuple[CorpusChunk, float]]) -> None:
        self._results = results
        self.calls = 0

    def search(
        self, query_embedding: list[float], top_k: int = 20
    ) -> list[tuple[CorpusChunk, float]]:
        self.calls += 1
        return self._results[:top_k]


class TestRetriever:
    def test_pipeline_returns_reranked_top_n(self) -> None:
        chunks = [
            _chunk("Modifier 25 distinct CC and separate exam", "a"),
            _chunk("Modifier 59 distinct procedures", "b"),
            _chunk("Plantar callus debridement", "c"),
            _chunk("Mastery of Modifier 25 four criteria", "d"),
        ]
        bm25 = BM25Index(chunks=chunks)
        # Dense returns chunks in a different order to exercise fusion.
        fake_dense = FakeDense(
            results=[
                (chunks[3], 0.9),
                (chunks[0], 0.85),
                (chunks[2], 0.5),
            ]
        )
        retriever = Retriever(
            bm25=bm25,
            dense=fake_dense,
            reranker=RerankerStub(top_n=2),
            embed=lambda _q: [0.0] * 8,
        )
        result = retriever.search("Modifier 25 distinct CC")
        assert result.query == "Modifier 25 distinct CC"
        assert len(result.chunks) == 2
        ids = [c.chunk_id for c, _ in result.chunks]
        # 'a' and 'd' both mention Modifier 25 + four criteria; one of them
        # must be at position 0 in the reranked output.
        assert ids[0] in {"a", "d"}
        assert fake_dense.calls == 1

    def test_pipeline_with_empty_dense_still_works(self) -> None:
        chunks = [_chunk("Modifier 25 distinct CC", "a")]
        retriever = Retriever(
            bm25=BM25Index(chunks=chunks),
            dense=FakeDense(results=[]),
            reranker=RerankerStub(top_n=5),
            embed=lambda _q: [0.0] * 8,
        )
        result = retriever.search("Modifier 25")
        assert len(result.chunks) == 1
