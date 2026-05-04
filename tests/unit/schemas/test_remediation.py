"""Unit tests for app.schemas.remediation."""

from __future__ import annotations

import pytest
from app.schemas.remediation import RemediationSuggestion
from app.schemas.text import Citation, TextSpan
from pydantic import ValidationError


def _policy_citation() -> Citation:
    return Citation(
        source_type="policy",
        span=TextSpan(text="x", start_char=0, end_char=1),
        policy_id="cms-foo",
        rationale="reason",
    )


class TestRemediationSuggestion:
    def test_construct(self) -> None:
        s = RemediationSuggestion(
            criterion="independent_mdm",
            suggested_addition="Document an independent decision...",
            motivation=[_policy_citation()],
        )
        assert s.criterion == "independent_mdm"

    def test_motivation_must_be_non_empty(self) -> None:
        with pytest.raises(ValidationError):
            RemediationSuggestion(
                criterion="distinct_cc",
                suggested_addition="x",
                motivation=[],
            )

    def test_invalid_criterion(self) -> None:
        with pytest.raises(ValidationError):
            RemediationSuggestion(
                criterion="bogus",  # type: ignore[arg-type]
                suggested_addition="x",
                motivation=[_policy_citation()],
            )

    def test_suggested_addition_length(self) -> None:
        with pytest.raises(ValidationError):
            RemediationSuggestion(
                criterion="distinct_cc",
                suggested_addition="",
                motivation=[_policy_citation()],
            )
        with pytest.raises(ValidationError):
            RemediationSuggestion(
                criterion="distinct_cc",
                suggested_addition="x" * 2001,
                motivation=[_policy_citation()],
            )

    def test_no_note_text_field(self) -> None:
        # Constitution Principle III: type-level guarantee that the Drafter
        # cannot modify the source note. The model must reject any extra
        # field.
        with pytest.raises(ValidationError):
            RemediationSuggestion(
                criterion="distinct_cc",
                suggested_addition="x",
                motivation=[_policy_citation()],
                note_text="please replace this",  # type: ignore[call-arg]
            )
