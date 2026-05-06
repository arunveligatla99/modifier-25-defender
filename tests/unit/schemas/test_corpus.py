"""Unit tests for app.schemas.corpus."""

from __future__ import annotations

from datetime import date

import pytest
from app.schemas.corpus import CorpusChunk
from pydantic import ValidationError


class TestCorpusChunk:
    def test_construct(self) -> None:
        c = CorpusChunk(
            chunk_id="cms-ncci-em-modifier25-2026-ch1-sec3",
            text="When a separately identifiable...",
            source_document="cms-ncci-policy-manual-2026.pdf",
            section_heading="Chapter 1, Section 3",
            publication_date=date(2026, 1, 1),
            authority_tier="CMS",
        )
        assert c.authority_tier == "CMS"

    def test_invalid_authority_tier(self) -> None:
        with pytest.raises(ValidationError):
            CorpusChunk(
                chunk_id="x",
                text="x",
                source_document="x",
                authority_tier="FDA",  # type: ignore[arg-type]
            )

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            CorpusChunk(  # type: ignore[call-arg]
                chunk_id="",
                text="x",
                source_document="x",
                authority_tier="OTHER",
            )
