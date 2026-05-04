"""Read manual clinical-reasonableness scores and compute the metric (T205).

Spec: AC-006-4 requires >=80% of remediation suggestions on a 20-sample
dev-split set to be judged clinically reasonable by a CPC-trained
reviewer (or careful self-review against the source policies).

The reviewer populates ``data/drafter_review/scores.jsonl``, one JSON
object per line:

    {"sample_id": "...", "reasonable": true, "notes": "..."}

When the scores file is absent or empty, the harness reports 0.0 so
the eval gate fails (intentional: the gate must not pass without
real review evidence).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SCORES_PATH = Path("data/drafter_review/scores.jsonl")
DEFAULT_SAMPLE_PATH = Path("data/drafter_review/dev_sample.jsonl")


@dataclass(frozen=True)
class ClinicalReasonablenessReport:
    """Output of the manual review aggregation.

    Attributes:
        total: Number of scored samples found.
        reasonable: Number marked ``reasonable: true``.
        rate: ``reasonable / total`` or 0.0 when no samples are scored.
        sample_ids_missing: Sample ids present in the dev_sample but
            absent from the scores file (so the reviewer can see what is
            still pending).
        per_sample: Map of sample_id -> reasonable bool, for surfacing
            in the eval report.
    """

    total: int
    reasonable: int
    rate: float
    sample_ids_missing: list[str] = field(default_factory=list)
    per_sample: dict[str, bool] = field(default_factory=dict)


def evaluate_clinical_reasonableness(
    scores_path: Path = DEFAULT_SCORES_PATH,
    sample_path: Path = DEFAULT_SAMPLE_PATH,
) -> ClinicalReasonablenessReport:
    """Aggregate the reviewer's per-sample verdicts into the metric."""
    sample_ids = _load_sample_ids(sample_path)
    score_records = list(_load_scores(scores_path))
    if not score_records:
        return ClinicalReasonablenessReport(
            total=0,
            reasonable=0,
            rate=0.0,
            sample_ids_missing=sample_ids,
            per_sample={},
        )

    per_sample: dict[str, bool] = {}
    for record in score_records:
        sample_id = record.get("sample_id")
        reasonable = bool(record.get("reasonable", False))
        if isinstance(sample_id, str):
            per_sample[sample_id] = reasonable

    total = len(per_sample)
    reasonable_count = sum(1 for ok in per_sample.values() if ok)
    rate = reasonable_count / total if total else 0.0
    missing = [sid for sid in sample_ids if sid not in per_sample]
    return ClinicalReasonablenessReport(
        total=total,
        reasonable=reasonable_count,
        rate=rate,
        sample_ids_missing=missing,
        per_sample=per_sample,
    )


def _load_sample_ids(sample_path: Path) -> list[str]:
    if not sample_path.exists():
        return []
    out: list[str] = []
    for line in sample_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        sid = record.get("sample_id")
        if isinstance(sid, str):
            out.append(sid)
    return out


def _load_scores(scores_path: Path) -> Iterable[dict[str, object]]:
    if not scores_path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in scores_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records
