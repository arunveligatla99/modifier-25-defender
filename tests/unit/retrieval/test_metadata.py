"""Unit tests for app.retrieval.metadata."""

from __future__ import annotations

from datetime import date

from app.retrieval.chunker import Chunk
from app.retrieval.metadata import build_chunk_id, enrich_chunk


class TestBuildChunkId:
    def test_idempotent(self) -> None:
        a = build_chunk_id("cms-ncci-em.pdf", 0, 100)
        b = build_chunk_id("cms-ncci-em.pdf", 0, 100)
        assert a == b

    def test_different_offsets_yield_different_ids(self) -> None:
        a = build_chunk_id("cms-ncci-em.pdf", 0, 100)
        b = build_chunk_id("cms-ncci-em.pdf", 50, 150)
        assert a != b

    def test_different_documents_yield_different_ids(self) -> None:
        a = build_chunk_id("cms-ncci-em.pdf", 0, 100)
        b = build_chunk_id("aapc-modifier25.html", 0, 100)
        assert a != b


class TestEnrichChunk:
    def test_round_trip_metadata(self) -> None:
        raw = Chunk(text="hello", token_count=1, start_token=0, end_token=5)
        cc = enrich_chunk(
            raw,
            source_document="cms-ncci-policy-manual.pdf",
            authority_tier="CMS",
            section_heading="Chapter 1, Section 3",
            publication_date=date(2026, 1, 1),
        )
        assert cc.text == "hello"
        assert cc.source_document == "cms-ncci-policy-manual.pdf"
        assert cc.authority_tier == "CMS"
        assert cc.section_heading == "Chapter 1, Section 3"
        assert cc.publication_date == date(2026, 1, 1)
        assert cc.chunk_id  # non-empty
