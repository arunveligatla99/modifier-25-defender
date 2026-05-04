"""Defensibility accuracy harness (T129).

For each encounter in the synthetic test split: run parser -> analyzer
and compare the analyzer's output to the ground-truth labels recorded by
the generator. Two metrics:

- ``verdict_accuracy`` (AC-004-2): fraction of overall verdicts that
  match ground truth. Lenient: a predicted WEAK is correct against
  either PASS or FAIL ground truth; only PASS-vs-FAIL confusions count
  as errors.
- ``per_criterion_accuracy`` (AC-004-3): per-criterion strict equality,
  averaged across the four criteria.

Inputs:

- ``data/synthetic/encounters/*.json``: SyntheticEncounter records
- ``data/synthetic/labels.jsonl``: per-encounter split membership and
  ground-truth labels

The harness only consumes encounters whose split == "test".
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.schemas.assessment import DefensibilityAssessment, Verdict
from app.schemas.parser import ParsedEncounter

from eval.schemas import SyntheticEncounter

logger = logging.getLogger(__name__)

DEFAULT_LABELS_PATH = Path("data/synthetic/labels.jsonl")
DEFAULT_ENCOUNTERS_DIR = Path("data/synthetic/encounters")
CRITERION_NAMES = ("distinct_cc", "separate_exam", "independent_mdm", "site_specificity")


class _ParserLike(Protocol):
    def parse(self, note_text: str) -> ParsedEncounter: ...


class _AnalyzerLike(Protocol):
    def score(
        self,
        parsed: ParsedEncounter,
        *,
        em_code: str,
        procedure_code: str,
        site: str | None,
    ) -> DefensibilityAssessment: ...


@dataclass(frozen=True)
class DefensibilityAccuracyReport:
    """Output of the defensibility accuracy harness.

    Attributes:
        total: Number of encounters evaluated.
        verdict_correct: Number whose overall verdict matches under the
            lenient AC-004-2 rule.
        verdict_accuracy: ``verdict_correct / total``.
        per_criterion_correct: Per-criterion strict-match counts.
        per_criterion_accuracy: ``correct/total`` averaged across the 4
            criteria.
        latency_p95_seconds: 95th percentile per-encounter latency, sorted
            ascending and indexed at the 95th percentile. Falls back to
            the max when fewer than 20 samples.
    """

    total: int
    verdict_correct: int
    verdict_accuracy: float
    per_criterion_correct: dict[str, int]
    per_criterion_accuracy: float
    latency_p95_seconds: float
    per_encounter: dict[str, dict[str, str]] = field(default_factory=dict)


def load_test_split(
    labels_path: Path = DEFAULT_LABELS_PATH,
    encounters_dir: Path = DEFAULT_ENCOUNTERS_DIR,
) -> list[SyntheticEncounter]:
    """Load synthetic encounters whose split is "test"."""
    if not labels_path.exists():
        return []
    test_ids: set[str] = set()
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("split") == "test":
            test_ids.add(record["encounter_id"])
    out: list[SyntheticEncounter] = []
    for eid in sorted(test_ids):
        path = encounters_dir / f"{eid}.json"
        if not path.exists():
            logger.warning("test encounter file missing: %s", path)
            continue
        out.append(SyntheticEncounter.model_validate_json(path.read_text(encoding="utf-8")))
    return out


def evaluate_defensibility_accuracy(
    parser: _ParserLike,
    analyzer: _AnalyzerLike,
    encounters: Iterable[SyntheticEncounter] | None = None,
    *,
    labels_path: Path = DEFAULT_LABELS_PATH,
    encounters_dir: Path = DEFAULT_ENCOUNTERS_DIR,
) -> DefensibilityAccuracyReport:
    """Run analyzer against the test split and compute accuracy metrics."""
    cases = (
        list(encounters)
        if encounters is not None
        else load_test_split(labels_path=labels_path, encounters_dir=encounters_dir)
    )
    if not cases:
        return DefensibilityAccuracyReport(
            total=0,
            verdict_correct=0,
            verdict_accuracy=0.0,
            per_criterion_correct={n: 0 for n in CRITERION_NAMES},
            per_criterion_accuracy=0.0,
            latency_p95_seconds=0.0,
            per_encounter={},
        )

    verdict_hits = 0
    crit_hits: dict[str, int] = {n: 0 for n in CRITERION_NAMES}
    latencies: list[float] = []
    per_enc: dict[str, dict[str, str]] = {}

    for enc in cases:
        t0 = time.perf_counter()
        parsed = parser.parse(enc.note_text)
        assessment = analyzer.score(
            parsed,
            em_code=enc.em_code,
            procedure_code=enc.procedure_code,
            site=enc.site,
        )
        latencies.append(time.perf_counter() - t0)

        gt_overall: Verdict = enc.ground_truth.overall
        pred_overall: Verdict = assessment.overall
        if _verdict_match_lenient(pred_overall, gt_overall):
            verdict_hits += 1

        criteria_record: dict[str, str] = {
            "overall_pred": pred_overall,
            "overall_gt": gt_overall,
        }
        for name in CRITERION_NAMES:
            pred = getattr(assessment.criteria, name).verdict
            gt = getattr(enc.ground_truth, name)
            criteria_record[f"{name}_pred"] = pred
            criteria_record[f"{name}_gt"] = gt
            if pred == gt:
                crit_hits[name] += 1
        per_enc[enc.encounter_id] = criteria_record

    total = len(cases)
    crit_accuracy = sum(crit_hits[n] / total for n in CRITERION_NAMES) / len(CRITERION_NAMES)
    return DefensibilityAccuracyReport(
        total=total,
        verdict_correct=verdict_hits,
        verdict_accuracy=verdict_hits / total,
        per_criterion_correct=crit_hits,
        per_criterion_accuracy=crit_accuracy,
        latency_p95_seconds=_percentile(latencies, 0.95),
        per_encounter=per_enc,
    )


def _verdict_match_lenient(pred: Verdict, gt: Verdict) -> bool:
    """AC-004-2 lenient match: WEAK is correct against any ground truth."""
    if pred == gt:
        return True
    if pred == "WEAK":
        return True
    if gt == "WEAK":
        # WEAK ground truth accepts any non-failure prediction. The spec
        # allows WEAK as a correct match for either PASS or FAIL; we
        # interpret this as: the predicted verdict cannot be the OPPOSITE
        # of the WEAK direction. Since WEAK is the middle, accept any.
        return True
    return False


def _percentile(values: list[float], pct: float) -> float:
    """Return the percentile value using nearest-rank.

    Falls back to ``max(values)`` when there are fewer than 20 samples,
    since interpolation on small samples is misleading.
    """
    if not values:
        return 0.0
    if len(values) < 20:
        return max(values)
    sorted_vals = sorted(values)
    idx = max(0, min(len(sorted_vals) - 1, round(pct * len(sorted_vals)) - 1))
    return sorted_vals[idx]
