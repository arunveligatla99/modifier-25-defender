"""Unit tests for app.schemas.api."""

from __future__ import annotations

import pytest
from app.schemas.api import DefenderRequest, DefenderResponse
from app.schemas.assessment import (
    CriteriaMap,
    CriterionScore,
    DefensibilityAssessment,
)
from app.schemas.parser import ParsedEncounter
from app.schemas.text import Citation, TextSpan
from pydantic import ValidationError


def _evidence() -> list[Citation]:
    return [
        Citation(
            source_type="encounter",
            span=TextSpan(text="x", start_char=0, end_char=1),
            rationale="why",
            entailed_paraphrase="x",
        )
    ]


def _passed_response() -> DefenderResponse:
    score = CriterionScore(verdict="PASS", confidence=1.0, evidence=_evidence())
    return DefenderResponse(
        encounter_id="enc-1",
        parsed=ParsedEncounter(),
        assessment=DefensibilityAssessment(
            overall="PASS",
            criteria=CriteriaMap(
                distinct_cc=score,
                separate_exam=score,
                independent_mdm=score,
                site_specificity=score,
            ),
        ),
        remediations=[],
        compliance_status="PASSED",
        blocked_reasons=None,
        trace_id="lf_t_local_1",
    )


class TestDefenderRequest:
    def _base(self, **overrides: object) -> dict[str, object]:
        defaults: dict[str, object] = {
            "encounter_id": "enc-1",
            "note_text": "CC: thick painful nails. ...",
            "em_code": "99213",
            "procedure_code": "11721",
            "modifier_25_attached": True,
            "site": "B",
        }
        defaults.update(overrides)
        return defaults

    def test_valid(self) -> None:
        DefenderRequest(**self._base())  # type: ignore[arg-type]

    def test_em_code_format(self) -> None:
        with pytest.raises(ValidationError):
            DefenderRequest(**self._base(em_code="99211"))  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            DefenderRequest(**self._base(em_code="abc"))  # type: ignore[arg-type]

    def test_procedure_code_format(self) -> None:
        with pytest.raises(ValidationError):
            DefenderRequest(**self._base(procedure_code="1234"))  # type: ignore[arg-type]

    def test_note_text_size_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DefenderRequest(**self._base(note_text=""))  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            DefenderRequest(**self._base(note_text="x" * 50_001))  # type: ignore[arg-type]

    def test_site_optional(self) -> None:
        DefenderRequest(**self._base(site=None))  # type: ignore[arg-type]

    def test_modifier_25_must_be_true(self) -> None:
        with pytest.raises(ValidationError):
            DefenderRequest(**self._base(modifier_25_attached=False))  # type: ignore[arg-type]


class TestDefenderResponse:
    def test_passed_response(self) -> None:
        r = _passed_response()
        assert r.compliance_status == "PASSED"
        assert r.blocked_reasons is None
        assert r.trace_id

    def test_blocked_response(self) -> None:
        r = DefenderResponse(
            encounter_id="enc-1",
            parsed=ParsedEncounter(),
            assessment=None,
            remediations=[],
            compliance_status="BLOCKED",
            blocked_reasons=["criterion=independent_mdm: claim not entailed"],
            trace_id="lf_t_local_1",
        )
        assert r.assessment is None
        assert r.blocked_reasons == ["criterion=independent_mdm: claim not entailed"]

    def test_trace_id_required(self) -> None:
        with pytest.raises(ValidationError):
            DefenderResponse(
                encounter_id="enc-1",
                parsed=ParsedEncounter(),
                assessment=None,
                remediations=[],
                compliance_status="BLOCKED",
                blocked_reasons=["x"],
                trace_id="",
            )
