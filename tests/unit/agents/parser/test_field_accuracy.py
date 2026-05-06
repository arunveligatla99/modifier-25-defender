"""Unit tests for the parser field-accuracy harness."""

from __future__ import annotations

from app.schemas.parser import ParsedEncounter
from app.schemas.text import TextSpan
from eval.parser.field_accuracy import (
    ParserEvalCase,
    evaluate_field_accuracy,
)


class FakeParser:
    def __init__(self, prediction: ParsedEncounter) -> None:
        self.prediction = prediction

    def parse(self, note_text: str) -> ParsedEncounter:
        return self.prediction


def _span(text: str, start: int, end: int) -> TextSpan:
    return TextSpan(text=text, start_char=start, end_char=end)


def test_perfect_prediction_yields_100_percent() -> None:
    cc = _span("thick painful nails", 0, 19)
    pred = ParsedEncounter(cc=[cc])
    case = ParserEvalCase(
        encounter_id="e1",
        note_text="thick painful nails",
        ground_truth={"cc": [cc], "hpi": [], "exam_findings": [], "mdm": [], "procedure_note": []},
    )
    report = evaluate_field_accuracy(FakeParser(pred), [case])
    assert report.total_fields == 5
    assert report.correct_fields == 5
    assert report.accuracy == 1.0


def test_field_within_120_percent_window_passes() -> None:
    pred = ParsedEncounter(cc=[_span("a" * 110, 0, 110)])
    case = ParserEvalCase(
        encounter_id="e1",
        note_text="a" * 200,
        ground_truth={
            "cc": [_span("b" * 100, 0, 100)],
            "hpi": [],
            "exam_findings": [],
            "mdm": [],
            "procedure_note": [],
        },
    )
    report = evaluate_field_accuracy(FakeParser(pred), [case])
    # cc within 80-120% (110/100 = 1.10), other 4 fields: 0/0 == correct.
    assert report.correct_fields == 5


def test_field_below_80_percent_fails() -> None:
    pred = ParsedEncounter(cc=[_span("x" * 70, 0, 70)])
    case = ParserEvalCase(
        encounter_id="e1",
        note_text="x" * 200,
        ground_truth={
            "cc": [_span("y" * 100, 0, 100)],
            "hpi": [],
            "exam_findings": [],
            "mdm": [],
            "procedure_note": [],
        },
    )
    report = evaluate_field_accuracy(FakeParser(pred), [case])
    # cc is wrong (70/100 = 0.70), other 4 are 0/0 correct.
    assert report.correct_fields == 4


def test_no_eval_cases_returns_zero() -> None:
    report = evaluate_field_accuracy(
        FakeParser(ParsedEncounter()),
        [],
    )
    assert report.total_fields == 0
    assert report.accuracy == 0.0
