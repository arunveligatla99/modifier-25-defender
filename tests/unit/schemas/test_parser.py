"""Unit tests for app.schemas.parser."""

from __future__ import annotations

import pytest
from app.schemas.parser import ParsedEncounter
from app.schemas.text import TextSpan
from pydantic import ValidationError


def _span(text: str, start: int, end: int) -> TextSpan:
    return TextSpan(text=text, start_char=start, end_char=end)


class TestParsedEncounter:
    def test_empty_lists_default(self) -> None:
        p = ParsedEncounter()
        assert p.cc == []
        assert p.ambiguous_segments == []

    def test_all_spans_excludes_ambiguous(self) -> None:
        cc = _span("nails", 0, 5)
        amb = _span("zzz", 100, 105)
        p = ParsedEncounter(cc=[cc], ambiguous_segments=[amb])
        assert cc in p.all_spans()
        assert amb not in p.all_spans()

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParsedEncounter(extra_field="oops")  # type: ignore[call-arg]

    def test_frozen(self) -> None:
        p = ParsedEncounter()
        with pytest.raises(ValidationError):
            p.cc = []  # type: ignore[misc]
