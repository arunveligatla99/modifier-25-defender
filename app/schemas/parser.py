"""Documentation Parser output schema.

Produced by EPIC-003. The parser returns a structured view of the encounter
note, with character offsets back into the source. Ambiguous segments are
surfaced explicitly per AC-003-3 rather than silently coerced.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.text import TextSpan


class ParsedEncounter(BaseModel):
    """Structured view of an encounter note.

    Attributes:
        cc: Chief complaint spans.
        hpi: History of present illness spans.
        exam_findings: Exam finding spans.
        mdm: Medical decision making spans.
        procedure_note: Procedure note spans.
        ambiguous_segments: Spans the parser could not classify cleanly.
            Surfacing per AC-003-3.

    Notes:
        The parser must validate its raw LLM output against this schema. A
        schema-invalid output triggers exactly one retry with the validation
        error fed back; a second failure surfaces a structured error to the
        Orchestrator (AC-003-4).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cc: list[TextSpan] = Field(default_factory=list)
    hpi: list[TextSpan] = Field(default_factory=list)
    exam_findings: list[TextSpan] = Field(default_factory=list)
    mdm: list[TextSpan] = Field(default_factory=list)
    procedure_note: list[TextSpan] = Field(default_factory=list)
    ambiguous_segments: list[TextSpan] = Field(default_factory=list)

    def all_spans(self) -> list[TextSpan]:
        """Return the union of all classified spans (excluding ambiguous)."""
        return [
            *self.cc,
            *self.hpi,
            *self.exam_findings,
            *self.mdm,
            *self.procedure_note,
        ]
