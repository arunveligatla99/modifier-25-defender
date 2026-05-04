"""Eval-only schemas for synthetic encounters and ground-truth labels.

Eval-only types intentionally live outside ``app/schemas/`` so that runtime
agents do not import test-set machinery. Keeping the boundary explicit means
synthesis-side imports stay clean and shipped artifacts contain only the
production schemas.
"""

from __future__ import annotations

from typing import Literal

from app.schemas.assessment import Verdict
from pydantic import BaseModel, ConfigDict, Field


class GroundTruthLabel(BaseModel):
    """Per-criterion and overall ground-truth labels for a synthetic encounter.

    Attributes:
        distinct_cc: Ground-truth verdict for the distinct CC criterion.
        separate_exam: Ground-truth verdict for the separate exam criterion.
        independent_mdm: Ground-truth verdict for the independent MDM criterion.
        site_specificity: Ground-truth verdict for the site-specificity criterion.
        overall: Deterministic aggregate of the four sub-labels.
        parameter_space_index: Records which slot value was chosen for each
            of the 12 parameter-space dimensions; lets the eval harness
            slice accuracy by dimension.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    distinct_cc: Verdict
    separate_exam: Verdict
    independent_mdm: Verdict
    site_specificity: Verdict
    overall: Verdict
    parameter_space_index: dict[str, str]


SplitName = Literal["train", "dev", "test"]
"""Train/dev/test split membership."""


class SyntheticEncounter(BaseModel):
    """A generated encounter with ground-truth labels.

    Attributes:
        encounter_id: Stable identifier; sortable by generation order.
        note_text: Generated clinical note.
        em_code: E/M code paired with this encounter.
        procedure_code: 5-digit CPT code paired with this encounter.
        site: Anatomical site; ``None`` when unspecified.
        ground_truth: Per-criterion + overall ground-truth labels.
        split: Train/dev/test membership (deterministic by ``encounter_id``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    encounter_id: str = Field(..., min_length=1)
    note_text: str = Field(..., min_length=1)
    em_code: str
    procedure_code: str
    site: Literal["L", "R", "B"] | None = None
    ground_truth: GroundTruthLabel
    split: SplitName
