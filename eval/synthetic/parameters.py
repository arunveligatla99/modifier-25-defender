"""12-dimension parameter space for synthetic encounter generation.

Spec EPIC-001 4.2 enumerates the dimensions; this module encodes them as
typed constants used by the templates and the generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

PresentingCondition = Literal[
    "thick_painful_nails",
    "callus_pain",
    "heel_pain",
    "plantar_fasciitis_followup",
    "diabetic_foot_check",
    "ankle_arthritis_flare",
    "hallux_pain",
    "ingrown_toenail",
]

ProcedureType = Literal[
    "nail_debridement_few",  # 11720
    "nail_debridement_many",  # 11721
    "callus_paring_single",  # 11055
    "callus_paring_few",  # 11056
    "callus_paring_many",  # 11057
    "joint_injection",  # 20600
]

EMLevel = Literal["99212", "99213", "99214", "99215"]

Site = Literal["L", "R", "B"] | None

NarrativeStyle = Literal["terse", "standard", "verbose"]

Separability = Literal["none", "low", "medium", "high"]

VerdictLabel = Literal["PASS", "WEAK", "FAIL"]


PROCEDURE_TYPE_TO_CPT: Final[dict[ProcedureType, str]] = {
    "nail_debridement_few": "11720",
    "nail_debridement_many": "11721",
    "callus_paring_single": "11055",
    "callus_paring_few": "11056",
    "callus_paring_many": "11057",
    "joint_injection": "20600",
}

PROCEDURE_TYPE_INDICATIONS: Final[dict[ProcedureType, str]] = {
    "nail_debridement_few": "thickened painful nails",
    "nail_debridement_many": "multiple thickened painful nails",
    "callus_paring_single": "painful plantar callus",
    "callus_paring_few": "multiple painful calluses",
    "callus_paring_many": "extensive callus burden with pain on ambulation",
    "joint_injection": "first MTP joint inflammation with refractory pain",
}


@dataclass(frozen=True)
class ParameterPoint:
    """A single point in the 12-dimension parameter space.

    Attributes:
        presenting_condition: Reason the patient came in.
        diabetes: Comorbidity flag.
        neuropathy: Comorbidity flag.
        pvd: Peripheral vascular disease flag.
        procedure_type: Which procedure is performed.
        site: Anatomical site for the procedure.
        em_level: Asserted E/M level on the claim.
        separable_problem: Whether a separable problem is documented at all.
        site_specificity_stated: Whether LT/RT or T1-T9 modifiers appear in
            the note's coding section.
        mdm_separability: How clearly the MDM addresses an independent
            problem.
        exam_separability: How clearly the exam documents non-procedure
            findings.
        narrative_style: Short / standard / verbose narrative style for
            template selection.
    """

    presenting_condition: PresentingCondition
    diabetes: bool
    neuropathy: bool
    pvd: bool
    procedure_type: ProcedureType
    site: Site
    em_level: EMLevel
    separable_problem: bool
    site_specificity_stated: bool
    mdm_separability: Separability
    exam_separability: Separability
    narrative_style: NarrativeStyle

    def as_index(self) -> dict[str, str]:
        """Return a dict suitable for ``GroundTruthLabel.parameter_space_index``."""
        return {
            "presenting_condition": self.presenting_condition,
            "diabetes": str(self.diabetes),
            "neuropathy": str(self.neuropathy),
            "pvd": str(self.pvd),
            "procedure_type": self.procedure_type,
            "site": self.site or "none",
            "em_level": self.em_level,
            "separable_problem": str(self.separable_problem),
            "site_specificity_stated": str(self.site_specificity_stated),
            "mdm_separability": self.mdm_separability,
            "exam_separability": self.exam_separability,
            "narrative_style": self.narrative_style,
        }
