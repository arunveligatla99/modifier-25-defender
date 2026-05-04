"""Defensibility Analyzer output schema.

Produced by EPIC-004. Implements the JARALL Standard four-criterion rubric
(distinct CC, separate exam findings, independent MDM, site-specificity).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.text import Citation

Verdict = Literal["PASS", "WEAK", "FAIL"]
"""Per-criterion or overall verdict."""


class CriterionScore(BaseModel):
    """Per-criterion verdict with cited evidence.

    Attributes:
        verdict: PASS, WEAK, or FAIL.
        confidence: Calibrated confidence in the verdict, 0.0..1.0.
        evidence: One or more citations that support the verdict.

    Notes:
        Empty ``evidence`` is a hard failure (AC-004-4 and Constitution
        Principle I). The Compliance Guard rejects any response that contains
        a ``CriterionScore`` with no citations.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[Citation] = Field(..., min_length=1)


class CriteriaMap(BaseModel):
    """The four JARALL Standard criteria, each scored independently."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    distinct_cc: CriterionScore
    separate_exam: CriterionScore
    independent_mdm: CriterionScore
    site_specificity: CriterionScore


class DefensibilityAssessment(BaseModel):
    """Aggregated four-criterion defensibility score.

    Attributes:
        overall: Deterministic aggregate of the four criteria.
        criteria: Per-criterion scores.

    Notes:
        ``overall`` is computed deterministically from the four sub-scores:
        any FAIL forces overall FAIL; any WEAK with no FAIL produces WEAK;
        all PASS produces PASS. The constructor validates this invariant.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall: Verdict
    criteria: CriteriaMap

    @model_validator(mode="after")
    def _check_overall(self) -> DefensibilityAssessment:
        """Ensure ``overall`` is the deterministic aggregate of the four sub-scores."""
        sub_verdicts = (
            self.criteria.distinct_cc.verdict,
            self.criteria.separate_exam.verdict,
            self.criteria.independent_mdm.verdict,
            self.criteria.site_specificity.verdict,
        )
        expected: Verdict
        if "FAIL" in sub_verdicts:
            expected = "FAIL"
        elif "WEAK" in sub_verdicts:
            expected = "WEAK"
        else:
            expected = "PASS"
        if self.overall != expected:
            raise ValueError(
                "DefensibilityAssessment: overall verdict must be the deterministic "
                f"aggregate of sub-scores (expected {expected!r}, got {self.overall!r})"
            )
        return self
