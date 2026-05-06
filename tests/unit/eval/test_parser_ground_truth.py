"""Unit tests for eval.parser.ground_truth."""

from __future__ import annotations

from eval.parser.ground_truth import build_eval_set_records, derive_spans
from eval.schemas import GroundTruthLabel, SyntheticEncounter


def _encounter(note: str) -> SyntheticEncounter:
    return SyntheticEncounter(
        encounter_id="e1",
        note_text=note,
        em_code="99213",
        procedure_code="11721",
        site="L",
        ground_truth=GroundTruthLabel(
            distinct_cc="PASS",
            separate_exam="PASS",
            independent_mdm="PASS",
            site_specificity="PASS",
            overall="PASS",
            parameter_space_index={},
        ),
        split="test",
    )


def test_terse_note_yields_one_span_per_section() -> None:
    note = (
        "CC: thick painful nails\n"
        "HPI: weeks of symptoms.\n"
        "Exam: nails examined.\n"
        "MDM: discussed.\n"
        "Procedure: Debridement performed."
    )
    spans = derive_spans(note)
    for field in ("cc", "hpi", "exam_findings", "mdm", "procedure_note"):
        assert len(spans[field]) == 1, f"{field}: expected one span"
        s = spans[field][0]
        # round-trip invariant: text must equal note slice
        assert note[s.start_char : s.end_char] == s.text


def test_standard_note_handles_double_newlines() -> None:
    note = (
        "CC: heel pain\n\n"
        "HPI: weeks of pain.\n\n"
        "Exam: tender heel.\n\n"
        "MDM: discussed.\n\n"
        "Procedure: Injection performed."
    )
    spans = derive_spans(note)
    assert spans["cc"][0].text == "heel pain"
    assert spans["procedure_note"][0].text == "Injection performed."


def test_verbose_trailer_is_stripped() -> None:
    note = (
        "CC: heel pain\n\n"
        "HPI: weeks.\n\n"
        "Exam: tender.\n\n"
        "MDM: discussed.\n\n"
        "Procedure: Injection.\n\n"
        "(End of note.)"
    )
    spans = derive_spans(note)
    proc = spans["procedure_note"][0]
    assert proc.text == "Injection."
    assert "(End of note.)" not in proc.text


def test_missing_marker_yields_empty_field() -> None:
    note = "CC: heel pain\nHPI: weeks.\nMDM: discussed.\nProcedure: Done."
    spans = derive_spans(note)
    assert spans["exam_findings"] == []
    assert len(spans["cc"]) == 1
    assert len(spans["hpi"]) == 1


def test_build_eval_set_records_round_trips() -> None:
    note = "CC: thick nails\nHPI: weeks.\nExam: nails.\nMDM: ok.\nProcedure: Done."
    records = build_eval_set_records([_encounter(note)])
    assert len(records) == 1
    rec = records[0]
    assert rec["encounter_id"] == "e1"
    assert rec["note_text"] == note
    cc_spans = rec["cc"]
    assert isinstance(cc_spans, list)
    assert cc_spans[0]["text"] == "thick nails"
    assert note[cc_spans[0]["start_char"] : cc_spans[0]["end_char"]] == "thick nails"
