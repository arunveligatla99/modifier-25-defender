"""Unit tests for the reranker stub."""

from __future__ import annotations

from app.retrieval.reranker import RerankerStub
from app.schemas.corpus import CorpusChunk


def _chunk(chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        text="x",
        source_document="x",
        authority_tier="OTHER",
    )


class TestRerankerStub:
    def test_sorts_by_descending_score(self) -> None:
        a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
        candidates = [(a, 0.1), (b, 0.9), (c, 0.5)]
        out = RerankerStub(top_n=3).rerank("any", candidates)
        assert [chunk.chunk_id for chunk, _ in out] == ["b", "c", "a"]

    def test_truncates_to_top_n(self) -> None:
        chunks = [(_chunk(f"c{i}"), float(i)) for i in range(10)]
        out = RerankerStub(top_n=5).rerank("q", chunks)
        assert len(out) == 5

    def test_empty_input(self) -> None:
        assert RerankerStub(top_n=5).rerank("q", []) == []
