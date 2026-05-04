"""API request and response schemas.

The top-level shape of ``POST /analyze``. See
``specs/001-modifier-25-defender/contracts/analyze-endpoint.md`` for the full
endpoint contract.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.assessment import DefensibilityAssessment
from app.schemas.parser import ParsedEncounter
from app.schemas.remediation import RemediationSuggestion

Site = Literal["L", "R", "B"]
"""Anatomical site: left, right, or bilateral. ``None`` when unspecified."""

ComplianceStatus = Literal["PASSED", "BLOCKED"]
"""Compliance Guard verdict (Q2 resolution: two-state in v1; DEGRADED deferred)."""

_EM_CODE_RE = re.compile(r"^9921[2-5]$")
_PROCEDURE_CODE_RE = re.compile(r"^[0-9]{5}$")


class DefenderRequest(BaseModel):
    """Request payload accepted by ``POST /analyze``.

    Attributes:
        encounter_id: Synthetic ID for tracking. Non-empty.
        note_text: Raw clinical note. 1 to 50,000 characters.
        em_code: E/M code, must match ``^9921[2-5]$`` for v1.
        procedure_code: 5-digit CPT code; full allowlist enforced at runtime.
        modifier_25_attached: Always ``True`` for v1.
        site: Optional anatomical site.

    Notes:
        PHI detection runs before any agent is invoked. A real-PHI marker in
        ``note_text`` returns HTTP 422 with a structured error citing
        Constitution Principle IV. Real-PHI handling is a v2 commitment behind
        a Business Associate Agreement.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    encounter_id: str = Field(..., min_length=1)
    note_text: str = Field(..., min_length=1, max_length=50_000)
    em_code: str
    procedure_code: str
    modifier_25_attached: Literal[True] = True
    site: Site | None = None

    @field_validator("em_code")
    @classmethod
    def _check_em_code(cls, value: str) -> str:
        """Validate E/M code format."""
        if not _EM_CODE_RE.match(value):
            raise ValueError(f"DefenderRequest: em_code must match ^9921[2-5]$, got {value!r}")
        return value

    @field_validator("procedure_code")
    @classmethod
    def _check_procedure_code(cls, value: str) -> str:
        """Validate procedure code is 5 digits. Allow-list check happens at runtime."""
        if not _PROCEDURE_CODE_RE.match(value):
            raise ValueError(f"DefenderRequest: procedure_code must be 5 digits, got {value!r}")
        return value


class DefenderResponse(BaseModel):
    """Response payload returned by ``POST /analyze``.

    Attributes:
        encounter_id: Echoed from request.
        parsed: Structured view of the encounter from EPIC-003.
        assessment: Four-criterion defensibility score from EPIC-004. ``None``
            when the response is BLOCKED.
        remediations: Targeted documentation suggestions. Empty when overall
            is PASS or when the Drafter is cut.
        compliance_status: ``"PASSED"`` or ``"BLOCKED"`` (two-state in v1
            per Q2 resolution; v1.1 will reintroduce a third state).
        blocked_reasons: Populated only when ``compliance_status == "BLOCKED"``.
        trace_id: Langfuse trace identifier; never empty (Constitution
            Principle V).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    encounter_id: str = Field(..., min_length=1)
    parsed: ParsedEncounter
    assessment: DefensibilityAssessment | None = None
    remediations: list[RemediationSuggestion] = Field(default_factory=list)
    compliance_status: ComplianceStatus
    blocked_reasons: list[str] | None = None
    trace_id: str = Field(..., min_length=1)
