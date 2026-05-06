"""Unit tests for app.schemas.assessment."""

from __future__ import annotations

import pytest
from app.schemas.assessment import (
    CriteriaMap,
    CriterionScore,
    DefensibilityAssessment,
    Verdict,
)
from app.schemas.text import Citation, TextSpan
from pydantic import ValidationError


def _ev(rationale: str = "explanation") -> Citation:
    return Citation(
        source_type="encounter",
        span=TextSpan(text="x", start_char=0, end_char=1),
        rationale=rationale,
        entailed_paraphrase="x",
    )


def _score(verdict: Verdict, confidence: float = 0.9) -> CriterionScore:
    return CriterionScore(verdict=verdict, confidence=confidence, evidence=[_ev()])


def _criteria(
    cc: Verdict = "PASS",
    se: Verdict = "PASS",
    mdm: Verdict = "PASS",
    ss: Verdict = "PASS",
) -> CriteriaMap:
    return CriteriaMap(
        distinct_cc=_score(cc),
        separate_exam=_score(se),
        independent_mdm=_score(mdm),
        site_specificity=_score(ss),
    )


class TestCriterionScore:
    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CriterionScore(verdict="PASS", confidence=-0.1, evidence=[_ev()])
        with pytest.raises(ValidationError):
            CriterionScore(verdict="PASS", confidence=1.1, evidence=[_ev()])

    def test_evidence_must_be_non_empty(self) -> None:
        with pytest.raises(ValidationError):
            CriterionScore(verdict="PASS", confidence=0.5, evidence=[])

    def test_invalid_verdict(self) -> None:
        with pytest.raises(ValidationError):
            CriterionScore(verdict="MAYBE", confidence=0.5, evidence=[_ev()])  # type: ignore[arg-type]


class TestDefensibilityAssessment:
    def test_all_pass(self) -> None:
        DefensibilityAssessment(overall="PASS", criteria=_criteria())

    def test_any_fail_forces_overall_fail(self) -> None:
        DefensibilityAssessment(overall="FAIL", criteria=_criteria(cc="FAIL"))
        with pytest.raises(ValidationError):
            DefensibilityAssessment(overall="WEAK", criteria=_criteria(cc="FAIL"))

    def test_weak_with_no_fail_forces_overall_weak(self) -> None:
        DefensibilityAssessment(overall="WEAK", criteria=_criteria(cc="WEAK"))
        with pytest.raises(ValidationError):
            DefensibilityAssessment(overall="PASS", criteria=_criteria(cc="WEAK"))

    def test_explicit_pass_when_all_pass(self) -> None:
        with pytest.raises(ValidationError):
            DefensibilityAssessment(overall="WEAK", criteria=_criteria())

    def test_fail_dominates_weak(self) -> None:
        DefensibilityAssessment(overall="FAIL", criteria=_criteria(cc="WEAK", se="FAIL"))
        with pytest.raises(ValidationError):
            DefensibilityAssessment(overall="WEAK", criteria=_criteria(cc="WEAK", se="FAIL"))
