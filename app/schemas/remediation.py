"""Remediation Drafter output schema.

Produced by EPIC-006. Suggestions are parallel structures, never edits to the
source note (AC-006-3, Constitution Principle III). Each suggestion targets
exactly one weak criterion and cites the policy that motivates it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.text import Citation

CriterionName = Literal[
    "distinct_cc",
    "separate_exam",
    "independent_mdm",
    "site_specificity",
]
"""Identifier for which criterion a remediation suggestion targets."""


class RemediationSuggestion(BaseModel):
    """A targeted documentation language suggestion for a weak criterion.

    Attributes:
        criterion: Which criterion the suggestion is intended to strengthen.
        suggested_addition: Clinician-facing language a coder could surface
            to the clinician for inclusion in the note. 1 to 2000 characters.
        motivation: One or more policy citations that motivate the suggestion.
            All citations have ``source_type == "policy"``.

    Notes:
        The Drafter MUST NOT modify the source note (AC-006-3); this is
        enforced at the type level by the absence of any ``note_text`` field
        on this model. Each weak or failing criterion in the assessment must
        have at least one corresponding suggestion (AC-006-1), and each
        suggestion must cite at least one policy chunk (AC-006-2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    criterion: CriterionName
    suggested_addition: str = Field(..., min_length=1, max_length=2000)
    motivation: list[Citation] = Field(..., min_length=1)
