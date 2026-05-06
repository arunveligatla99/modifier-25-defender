"""Slot-fill templates for synthetic encounter notes.

Each section (CC, HPI, Exam, MDM, Procedure) has a small bank of fragments
varied by parameter values. Fragments are intentionally short and clinically
plausible without aiming for medical-textbook fidelity. The 20-encounter
manual review (AC-001-7, T107) is the safety net for catching drift.

The label rules below ARE the operational definitions of the JARALL Standard
criteria for the purpose of generated ground truth. See spec EPIC-004 7.1
for the source-of-truth criterion definitions; this module compiles those
into deterministic label functions.
"""

from __future__ import annotations

from app.schemas.assessment import Verdict

from eval.synthetic.parameters import (
    PROCEDURE_TYPE_INDICATIONS,
    ParameterPoint,
    Separability,
)

# ---------------------------------------------------------------------------
# Section fragments
# ---------------------------------------------------------------------------

CC_FRAGMENTS: dict[str, dict[bool, list[str]]] = {
    "thick_painful_nails": {
        False: ["thick painful nails"],
        True: ["thick painful nails plus new heel pain on ambulation"],
    },
    "callus_pain": {
        False: ["painful callus on the foot"],
        True: ["painful callus and new burning sensation in the forefoot"],
    },
    "heel_pain": {
        False: ["new heel pain after long walk"],
        True: ["new heel pain plus right ankle swelling"],
    },
    "plantar_fasciitis_followup": {
        False: ["follow up plantar fasciitis"],
        True: ["follow up plantar fasciitis with new lateral foot pain"],
    },
    "diabetic_foot_check": {
        False: ["routine diabetic foot evaluation"],
        True: ["diabetic foot evaluation with new dorsal swelling"],
    },
    "ankle_arthritis_flare": {
        False: ["ankle arthritis flare"],
        True: ["ankle arthritis flare with new contralateral knee pain"],
    },
    "hallux_pain": {
        False: ["hallux MTP pain"],
        True: ["hallux MTP pain with new midfoot stiffness"],
    },
    "ingrown_toenail": {
        False: ["ingrown toenail"],
        True: ["ingrown toenail and unrelated lesser-toe corn"],
    },
}


def _exam_for_separability(separability: Separability, site_text: str, indication: str) -> str:
    """Return an exam-findings paragraph that scores at the given separability level."""
    if separability == "none":
        return f"Exam: {site_text} consistent with {indication}; no other findings recorded."
    if separability == "low":
        return (
            f"Exam: {site_text} consistent with {indication}; "
            "general inspection of the foot otherwise unremarkable."
        )
    if separability == "medium":
        return (
            f"Exam: {site_text} consistent with {indication}. "
            "Additional finding: mild tenderness at a separate site."
        )
    return (
        f"Exam: {site_text} consistent with {indication}. "
        "Separately identified: tenderness at a distinct anatomic location with "
        "documented quality, palpable swelling, and pain on resisted motion."
    )


def _mdm_for_separability(separability: Separability) -> str:
    """Return an MDM paragraph that scores at the given separability level."""
    if separability == "none":
        return "MDM: discussed risks and benefits of the planned procedure; patient consents."
    if separability == "low":
        return (
            "MDM: discussed risks and benefits of the planned procedure; patient consents. "
            "Mentioned other complaints, no separate management plan."
        )
    if separability == "medium":
        return (
            "MDM: addressed the procedure as well as a separate complaint; "
            "considered conservative options for the separate complaint and deferred a decision."
        )
    return (
        "MDM: addressed an independent problem with risks, data review (X-ray pending), "
        "and a management plan distinct from the procedure decision; "
        "shared decision making documented."
    )


def _site_text(point: ParameterPoint) -> str:
    """Anatomic site phrasing used in the exam fragment."""
    if point.procedure_type.startswith("nail_debridement"):
        return "nails examined"
    if point.procedure_type.startswith("callus_paring"):
        return "plantar callus area"
    return "first MTP joint"


def _site_modifier_phrase(point: ParameterPoint) -> str:
    """Return the LT/RT/T-modifier phrasing used in the procedure section."""
    if not point.site_specificity_stated:
        return ""
    if point.site == "L":
        return " (LT modifier documented)"
    if point.site == "R":
        return " (RT modifier documented)"
    if point.site == "B":
        return " (LT and RT modifiers documented)"
    return ""


# ---------------------------------------------------------------------------
# Procedure section bodies, keyed by procedure type
# ---------------------------------------------------------------------------

_PROCEDURE_BODIES: dict[str, str] = {
    "nail_debridement_few": (
        "Debridement of 1 to 5 thickened nails performed with sterile technique"
    ),
    "nail_debridement_many": (
        "Debridement of 6 or more thickened nails performed with sterile technique"
    ),
    "callus_paring_single": "Paring of single hyperkeratotic lesion performed",
    "callus_paring_few": "Paring of multiple hyperkeratotic lesions performed",
    "callus_paring_many": "Paring of extensive hyperkeratotic lesions performed",
    "joint_injection": ("Aspiration and corticosteroid injection of the first MTP joint performed"),
}


# ---------------------------------------------------------------------------
# Note assembly
# ---------------------------------------------------------------------------


def render_note(point: ParameterPoint) -> str:
    """Render a clinical note from a parameter-space point.

    Args:
        point: The parameter-space point.

    Returns:
        A multi-line note text using the canonical CC / HPI / Exam / MDM /
        Procedure structure.
    """
    cc_text = CC_FRAGMENTS[point.presenting_condition][point.separable_problem][0]
    indication = PROCEDURE_TYPE_INDICATIONS[point.procedure_type]
    exam = _exam_for_separability(point.exam_separability, _site_text(point), indication)
    mdm = _mdm_for_separability(point.mdm_separability)

    hpi_pieces: list[str] = []
    duration = "6 months" if point.narrative_style == "verbose" else "weeks"
    hpi_pieces.append(f"HPI: {duration} of symptoms relating to {indication}.")
    if point.separable_problem:
        hpi_pieces.append("Patient also reports a distinct symptom requiring separate evaluation.")
    if point.diabetes:
        hpi_pieces.append("PMH: Type 2 diabetes mellitus.")
    if point.neuropathy:
        hpi_pieces.append("Sensory neuropathy noted on prior visits.")
    if point.pvd:
        hpi_pieces.append("Peripheral vascular disease noted.")

    procedure_body = _PROCEDURE_BODIES[point.procedure_type]
    procedure = (
        f"Procedure: {procedure_body}{_site_modifier_phrase(point)}. "
        "Tolerated well, no immediate complications."
    )

    parts: list[str] = [
        f"CC: {cc_text}",
        " ".join(hpi_pieces),
        exam,
        mdm,
        procedure,
    ]
    if point.narrative_style == "terse":
        return "\n".join(parts)
    if point.narrative_style == "standard":
        return "\n\n".join(parts)
    return "\n\n".join(parts) + "\n\n(End of note.)"


# ---------------------------------------------------------------------------
# Ground-truth labeling
# ---------------------------------------------------------------------------


def _label_distinct_cc(point: ParameterPoint) -> Verdict:
    """Label the distinct CC criterion based on parameter values."""
    if point.separable_problem:
        return "PASS"
    return "FAIL"


def _label_separate_exam(point: ParameterPoint) -> Verdict:
    """Label the separate exam criterion."""
    return _separability_to_verdict(point.exam_separability)


def _label_independent_mdm(point: ParameterPoint) -> Verdict:
    """Label the independent MDM criterion."""
    return _separability_to_verdict(point.mdm_separability)


def _label_site_specificity(point: ParameterPoint) -> Verdict:
    """Label the site-specificity criterion.

    Per spec EPIC-004 Criterion 4: PASS when E/M and procedure are on
    different sites with both modifiers documented; WEAK when different
    sites are implied but not modifier-coded; FAIL when same-site E/M and
    procedure without separable problem documentation.
    """
    if point.site is None:
        # Same-site or unspecified: defaults to PASS unless no separable
        # problem is documented anywhere (in which case the verdict is FAIL).
        return "PASS" if point.separable_problem else "FAIL"
    if point.site_specificity_stated:
        return "PASS"
    return "WEAK"


def _separability_to_verdict(s: Separability) -> Verdict:
    if s == "none":
        return "FAIL"
    if s == "low":
        return "FAIL"
    if s == "medium":
        return "WEAK"
    return "PASS"


def label_for(point: ParameterPoint) -> tuple[Verdict, Verdict, Verdict, Verdict, Verdict]:
    """Return the five labels (four sub-criteria plus overall) for a point.

    The overall verdict is the deterministic aggregate per spec EPIC-004 7.2.
    """
    distinct_cc = _label_distinct_cc(point)
    separate_exam = _label_separate_exam(point)
    independent_mdm = _label_independent_mdm(point)
    site_specificity = _label_site_specificity(point)
    sub = (distinct_cc, separate_exam, independent_mdm, site_specificity)
    if "FAIL" in sub:
        overall: Verdict = "FAIL"
    elif "WEAK" in sub:
        overall = "WEAK"
    else:
        overall = "PASS"
    return distinct_cc, separate_exam, independent_mdm, site_specificity, overall
