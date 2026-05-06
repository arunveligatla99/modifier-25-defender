"""Unit tests for eval.defensibility.accuracy."""

from __future__ import annotations

from app.schemas.assessment import (
    CriteriaMap,
    CriterionScore,
    DefensibilityAssessment,
)
from app.schemas.parser import ParsedEncounter
from app.schemas.text import Citation, TextSpan
from eval.defensibility.accuracy import evaluate_defensibility_accuracy
from eval.schemas import GroundTruthLabel, SyntheticEncounter


def _citation(text: str = "x") -> Citation:
    return Citation(
        source_type="encounter",
        span=TextSpan(text=text, start_char=0, end_char=len(text)),
        rationale="test rationale",
        entailed_paraphrase=text,
    )


def _score(verdict: str) -> CriterionScore:
    return CriterionScore(
        verdict=verdict,
        confidence=0.8,
        evidence=[_citation()],
    )


def _assessment(
    distinct_cc: str,
    separate_exam: str,
    independent_mdm: str,
    site_specificity: str,
    overall: str,
) -> DefensibilityAssessment:
    return DefensibilityAssessment(
        overall=overall,
        criteria=CriteriaMap(
            distinct_cc=_score(distinct_cc),
            separate_exam=_score(separate_exam),
            independent_mdm=_score(independent_mdm),
            site_specificity=_score(site_specificity),
        ),
    )


def _encounter(
    eid: str,
    distinct_cc: str,
    separate_exam: str,
    independent_mdm: str,
    site_specificity: str,
    overall: str,
) -> SyntheticEncounter:
    return SyntheticEncounter(
        encounter_id=eid,
        note_text="The patient has a complaint.",
        em_code="99213",
        procedure_code="11721",
        site="L",
        ground_truth=GroundTruthLabel(
            distinct_cc=distinct_cc,
            separate_exam=separate_exam,
            independent_mdm=independent_mdm,
            site_specificity=site_specificity,
            overall=overall,
            parameter_space_index={},
        ),
        split="test",
    )


class StubParser:
    def parse(self, note_text: str) -> ParsedEncounter:
        return ParsedEncounter(
            cc=[],
            hpi=[],
            exam_findings=[],
            mdm=[],
            procedure_note=[],
            ambiguous_segments=[],
        )


class StubAnalyzer:
    """Returns a canned assessment per encounter via constructor mapping."""

    def __init__(self, mapping: dict[str, DefensibilityAssessment]) -> None:
        self.mapping = mapping
        self.last_query: tuple[str, str, str | None] | None = None

    def score(
        self,
        parsed: ParsedEncounter,
        *,
        em_code: str,
        procedure_code: str,
        site: str | None,
    ) -> DefensibilityAssessment:
        self.last_query = (em_code, procedure_code, site)
        # Use first key in mapping that hasn't been served. Caller controls
        # ordering by passing matched encounter list.
        return next(iter(self.mapping.values()))


def test_perfect_match_yields_full_accuracy() -> None:
    enc = _encounter("e1", "PASS", "PASS", "PASS", "PASS", "PASS")
    analyzer = StubAnalyzer({enc.encounter_id: _assessment("PASS", "PASS", "PASS", "PASS", "PASS")})
    report = evaluate_defensibility_accuracy(StubParser(), analyzer, [enc])
    assert report.total == 1
    assert report.verdict_correct == 1
    assert report.verdict_accuracy == 1.0
    assert report.per_criterion_accuracy == 1.0


def test_lenient_weak_matches_pass_ground_truth() -> None:
    enc = _encounter("e1", "PASS", "PASS", "PASS", "PASS", "PASS")
    analyzer = StubAnalyzer({enc.encounter_id: _assessment("WEAK", "PASS", "PASS", "PASS", "WEAK")})
    report = evaluate_defensibility_accuracy(StubParser(), analyzer, [enc])
    # Lenient: predicted overall WEAK against PASS gt counts as correct.
    assert report.verdict_correct == 1
    # Strict: distinct_cc WEAK != PASS gt -> mismatch on that criterion only.
    assert report.per_criterion_correct["distinct_cc"] == 0
    assert report.per_criterion_correct["separate_exam"] == 1


def test_pass_vs_fail_is_an_error() -> None:
    enc = _encounter("e1", "PASS", "PASS", "PASS", "PASS", "PASS")
    analyzer = StubAnalyzer({enc.encounter_id: _assessment("FAIL", "FAIL", "FAIL", "FAIL", "FAIL")})
    report = evaluate_defensibility_accuracy(StubParser(), analyzer, [enc])
    assert report.verdict_correct == 0
    assert report.per_criterion_accuracy == 0.0


def test_empty_split_returns_zeroed_report() -> None:
    report = evaluate_defensibility_accuracy(StubParser(), StubAnalyzer({}), [])
    assert report.total == 0
    assert report.verdict_accuracy == 0.0
    assert report.per_criterion_accuracy == 0.0
