"""Unit tests for app.retrieval.chunker."""

from __future__ import annotations

import pytest
from app.retrieval.chunker import Chunk, ChunkerConfig, chunk_document


class TestChunkDocument:
    def test_empty_text_returns_empty_list(self) -> None:
        assert chunk_document("") == []
        assert chunk_document("   \n\t  ") == []

    def test_short_document_single_chunk(self) -> None:
        text = "short content here"
        chunks = chunk_document(text)
        assert len(chunks) == 1
        c = chunks[0]
        assert isinstance(c, Chunk)
        assert c.token_count > 0
        assert c.start_token == 0

    def test_long_document_overlapping_chunks(self) -> None:
        # 1000 distinct word-sized tokens; with target=300/overlap=50, expect
        # ceil((1000-50)/(300-50)) = 4 chunks (the last one shorter).
        words = [f"w{i:04d}" for i in range(1000)]
        text = " ".join(words)
        chunks = chunk_document(text)
        assert len(chunks) >= 3
        # Coverage: union of (start_token..end_token) covers token 0..len.
        first = chunks[0]
        last = chunks[-1]
        assert first.start_token == 0
        assert last.end_token >= 999

    def test_overlap_between_neighbors(self) -> None:
        from itertools import pairwise

        words = [f"word{i:04d}" for i in range(800)]
        text = " ".join(words)
        cfg = ChunkerConfig(target_tokens=200, overlap_tokens=50, max_tokens=200)
        chunks = chunk_document(text, cfg)
        assert len(chunks) >= 2
        for prev, nxt in pairwise(chunks):
            assert nxt.start_token <= prev.end_token

    def test_invalid_overlap_raises(self) -> None:
        with pytest.raises(ValueError):
            chunk_document("hello", ChunkerConfig(target_tokens=100, overlap_tokens=100))
        with pytest.raises(ValueError):
            chunk_document("hello", ChunkerConfig(target_tokens=200, max_tokens=100))
