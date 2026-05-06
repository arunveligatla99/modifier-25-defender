"""Unit tests for app.retrieval.bm25."""

from __future__ import annotations

import pytest
from app.retrieval.bm25 import BM25Index, tokenize
from app.schemas.corpus import CorpusChunk


def _chunk(text: str, chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        text=text,
        source_document="x",
        authority_tier="OTHER",
    )


class TestTokenize:
    def test_lowercases_and_splits(self) -> None:
        assert tokenize("Modifier 25 Defender") == ["modifier", "25", "defender"]

    def test_strips_punctuation(self) -> None:
        assert tokenize("CMS-NCCI: Modifier 25!") == ["cms", "ncci", "modifier", "25"]

    def test_empty(self) -> None:
        assert tokenize("") == []


@pytest.fixture
def small_index() -> BM25Index:
    return BM25Index(
        chunks=[
            _chunk("CMS Modifier 25 guidance for E/M with minor procedure", "a"),
            _chunk("AAPC article on Modifier 59 for distinct procedures", "b"),
            _chunk("Plantar callus debridement with sterile technique", "c"),
            _chunk("Modifier 25 mastery: distinct CC, separate exam", "d"),
        ]
    )


class TestBM25Index:
    def test_returns_ranked_chunks(self, small_index: BM25Index) -> None:
        results = small_index.search("Modifier 25 distinct CC", top_k=3)
        assert results
        ids = [c.chunk_id for c, _ in results]
        # Most relevant chunks should appear before the unrelated debridement chunk.
        assert "d" in ids[:2]
        assert "a" in ids[:3]

    def test_empty_query_returns_empty(self, small_index: BM25Index) -> None:
        assert small_index.search("", top_k=5) == []
        assert small_index.search("!!!", top_k=5) == []

    def test_top_k_truncates(self, small_index: BM25Index) -> None:
        assert len(small_index.search("Modifier", top_k=2)) <= 2

    def test_empty_index(self) -> None:
        idx = BM25Index(chunks=[])
        assert idx.search("anything") == []
