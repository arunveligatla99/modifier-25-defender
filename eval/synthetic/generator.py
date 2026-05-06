"""Deterministic synthetic encounter generator.

Combines the parameter space (:mod:`eval.synthetic.parameters`) with the
slot-fill templates (:mod:`eval.synthetic.templates`) to produce a stream of
labeled :class:`SyntheticEncounter` objects. The generator is fully
deterministic given a seed (AC-001-6).
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterator

from eval.schemas import GroundTruthLabel, SyntheticEncounter
from eval.synthetic.parameters import (
    PROCEDURE_TYPE_TO_CPT,
    EMLevel,
    NarrativeStyle,
    ParameterPoint,
    PresentingCondition,
    ProcedureType,
    Separability,
    Site,
)
from eval.synthetic.split import split_for
from eval.synthetic.templates import label_for, render_note

PRESENTING_CONDITIONS: tuple[PresentingCondition, ...] = (
    "thick_painful_nails",
    "callus_pain",
    "heel_pain",
    "plantar_fasciitis_followup",
    "diabetic_foot_check",
    "ankle_arthritis_flare",
    "hallux_pain",
    "ingrown_toenail",
)
PROCEDURE_TYPES: tuple[ProcedureType, ...] = tuple(PROCEDURE_TYPE_TO_CPT.keys())
EM_LEVELS: tuple[EMLevel, ...] = ("99212", "99213", "99214", "99215")
SITES: tuple[Site, ...] = ("L", "R", "B", None)
NARRATIVE_STYLES: tuple[NarrativeStyle, ...] = ("terse", "standard", "verbose")
SEPARABILITY_LEVELS: tuple[Separability, ...] = ("none", "low", "medium", "high")


def random_point(rng: random.Random) -> ParameterPoint:
    """Sample a uniformly random point from the parameter space."""
    return ParameterPoint(
        presenting_condition=rng.choice(PRESENTING_CONDITIONS),
        diabetes=rng.random() < 0.4,
        neuropathy=rng.random() < 0.3,
        pvd=rng.random() < 0.2,
        procedure_type=rng.choice(PROCEDURE_TYPES),
        site=rng.choice(SITES),
        em_level=rng.choice(EM_LEVELS),
        separable_problem=rng.random() < 0.5,
        site_specificity_stated=rng.random() < 0.5,
        mdm_separability=rng.choice(SEPARABILITY_LEVELS),
        exam_separability=rng.choice(SEPARABILITY_LEVELS),
        narrative_style=rng.choice(NARRATIVE_STYLES),
    )


def _encounter_id(index: int, point: ParameterPoint) -> str:
    """Stable encounter ID combining a sequence index and a parameter hash.

    The leading 4-digit zero-padded index keeps lexicographic order matching
    generation order. The trailing hash makes IDs robust to parameter-space
    extensions while still being deterministic.
    """
    payload = f"{point.presenting_condition}|{point.procedure_type}|{point.site}|{point.em_level}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
    return f"synth_{index:04d}_{digest}"


def encounter_from_point(index: int, point: ParameterPoint) -> SyntheticEncounter:
    """Render a :class:`SyntheticEncounter` from a parameter point.

    Args:
        index: Sequence index used in the encounter ID.
        point: The parameter-space point.

    Returns:
        A :class:`SyntheticEncounter` with note text, codes, ground-truth
        labels, and split membership populated.
    """
    distinct_cc, separate_exam, independent_mdm, site_specificity, overall = label_for(point)
    eid = _encounter_id(index, point)
    label = GroundTruthLabel(
        distinct_cc=distinct_cc,
        separate_exam=separate_exam,
        independent_mdm=independent_mdm,
        site_specificity=site_specificity,
        overall=overall,
        parameter_space_index=point.as_index(),
    )
    return SyntheticEncounter(
        encounter_id=eid,
        note_text=render_note(point),
        em_code=point.em_level,
        procedure_code=PROCEDURE_TYPE_TO_CPT[point.procedure_type],
        site=point.site,
        ground_truth=label,
        split=split_for(eid),
    )


def generate(seed: int, count: int) -> Iterator[SyntheticEncounter]:
    """Yield ``count`` synthetic encounters from a deterministic stream.

    Args:
        seed: Generator seed. Default 42 (Q4 / AC-001-6).
        count: Number of encounters to yield.

    Yields:
        :class:`SyntheticEncounter` instances in generation order.
    """
    rng = random.Random(seed)
    for index in range(count):
        point = random_point(rng)
        yield encounter_from_point(index, point)
