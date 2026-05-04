"""Unit tests for app.schemas.text."""

from __future__ import annotations

import pytest
from app.schemas.text import Citation, TextSpan
from pydantic import ValidationError


class TestTextSpan:
    def test_construct_valid_span(self) -> None:
        span = TextSpan(text="thick painful nails", start_char=4, end_char=23)
        assert span.length() == 19

    def test_end_must_exceed_start(self) -> None:
        with pytest.raises(ValidationError):
            TextSpan(text="x", start_char=10, end_char=10)
        with pytest.raises(ValidationError):
            TextSpan(text="x", start_char=10, end_char=5)

    def test_negative_offsets_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TextSpan(text="x", start_char=-1, end_char=5)

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TextSpan(text="", start_char=0, end_char=1)

    def test_matches_source_invariant(self) -> None:
        source = "CC: thick painful nails. HPI: ..."
        span = TextSpan(text="thick painful nails", start_char=4, end_char=23)
        assert span.matches_source(source)

    def test_matches_source_negative_when_offsets_misalign(self) -> None:
        source = "abc def ghi"
        span = TextSpan(text="def", start_char=3, end_char=6)
        # span.text says "def" but source[3:6] is " de"
        assert not span.matches_source(source)

    def test_matches_source_handles_oob(self) -> None:
        source = "short"
        span = TextSpan(text="long", start_char=0, end_char=10)
        assert not span.matches_source(source)

    def test_frozen(self) -> None:
        span = TextSpan(text="x", start_char=0, end_char=1)
        with pytest.raises(ValidationError):
            span.text = "y"  # type: ignore[misc]


class TestCitation:
    def _span(self) -> TextSpan:
        return TextSpan(text="x", start_char=0, end_char=1)

    def test_encounter_citation_no_policy_id(self) -> None:
        c = Citation(
            source_type="encounter",
            span=self._span(),
            rationale="explanation",
            entailed_paraphrase="x is the cited content.",
        )
        assert c.policy_id is None

    def test_encounter_citation_rejects_policy_id(self) -> None:
        with pytest.raises(ValidationError):
            Citation(
                source_type="encounter",
                span=self._span(),
                policy_id="cms-foo",
                rationale="explanation",
                entailed_paraphrase="x",
            )

    def test_policy_citation_requires_policy_id(self) -> None:
        with pytest.raises(ValidationError):
            Citation(
                source_type="policy",
                span=self._span(),
                rationale="explanation",
                entailed_paraphrase="x",
            )

    def test_policy_citation_with_id(self) -> None:
        c = Citation(
            source_type="policy",
            span=self._span(),
            policy_id="cms-ncci-em-modifier25-2026-ch1-sec3",
            rationale="explanation",
            entailed_paraphrase="paraphrase of policy span",
        )
        assert c.policy_id is not None

    def test_rationale_length_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Citation(
                source_type="encounter",
                span=self._span(),
                rationale="",
                entailed_paraphrase="x",
            )
        with pytest.raises(ValidationError):
            Citation(
                source_type="encounter",
                span=self._span(),
                rationale="x" * 1001,
                entailed_paraphrase="x",
            )

    def test_entailed_paraphrase_required(self) -> None:
        with pytest.raises(ValidationError):
            Citation(  # type: ignore[call-arg]
                source_type="encounter",
                span=self._span(),
                rationale="x",
            )

    def test_entailed_paraphrase_length_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Citation(
                source_type="encounter",
                span=self._span(),
                rationale="x",
                entailed_paraphrase="",
            )
        with pytest.raises(ValidationError):
            Citation(
                source_type="encounter",
                span=self._span(),
                rationale="x",
                entailed_paraphrase="y" * 501,
            )
