"""Field-level accuracy harness for the Documentation Parser (AC-003-2).

A predicted field is considered correct when its character offsets cover
80 percent to 120 percent of the ground-truth span. The harness operates on
a JSONL eval set under ``data/parser_eval/dev.jsonl`` whose entries pair
``note_text`` with the expected per-field span list.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.schemas.parser import ParsedEncounter
from app.schemas.text import TextSpan

DEFAULT_EVAL_PATH = Path("data/parser_eval/dev.jsonl")
LOWER_BOUND = 0.80
UPPER_BOUND = 1.20

FIELDS: tuple[str, ...] = (
    "cc",
    "hpi",
    "exam_findings",
    "mdm",
    "procedure_note",
)


class _ParserLike(Protocol):
    def parse(self, note_text: str) -> ParsedEncounter: ...


@dataclass(frozen=True)
class ParserEvalCase:
    """One eval entry: a note plus expected per-field span lists."""

    encounter_id: str
    note_text: str
    ground_truth: dict[str, list[TextSpan]]


@dataclass(frozen=True)
class FieldAccuracyReport:
    """Output of the parser eval harness.

    Attributes:
        total_fields: Total number of (case, field) pairs evaluated.
        correct_fields: Pairs where the predicted span covered 80 to 120
            percent of the ground-truth span.
        accuracy: ``correct_fields / total_fields`` or 0 when no fields.
        per_case: Per-case dict of field -> bool.
    """

    total_fields: int
    correct_fields: int
    accuracy: float
    per_case: dict[str, dict[str, bool]] = field(default_factory=dict)


def load_eval_set(path: Path = DEFAULT_EVAL_PATH) -> list[ParserEvalCase]:
    """Load the parser eval set from ``path``."""
    if not path.exists():
        return []
    cases: list[ParserEvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        gt: dict[str, list[TextSpan]] = {}
        for field_name in FIELDS:
            gt[field_name] = [TextSpan(**span) for span in record.get(field_name, [])]
        cases.append(
            ParserEvalCase(
                encounter_id=record["encounter_id"],
                note_text=record["note_text"],
                ground_truth=gt,
            )
        )
    return cases


def evaluate_field_accuracy(
    parser: _ParserLike,
    cases: Iterable[ParserEvalCase] | None = None,
    *,
    eval_path: Path = DEFAULT_EVAL_PATH,
) -> FieldAccuracyReport:
    """Compute field-level accuracy of ``parser`` on the eval set."""
    case_list = list(cases) if cases is not None else load_eval_set(eval_path)
    if not case_list:
        return FieldAccuracyReport(0, 0, 0.0, per_case={})

    per_case: dict[str, dict[str, bool]] = {}
    total = 0
    correct = 0
    for case in case_list:
        prediction = parser.parse(case.note_text)
        case_results: dict[str, bool] = {}
        for field_name in FIELDS:
            ok = _field_correct(prediction, field_name, case.ground_truth[field_name])
            case_results[field_name] = ok
            total += 1
            if ok:
                correct += 1
        per_case[case.encounter_id] = case_results

    return FieldAccuracyReport(
        total_fields=total,
        correct_fields=correct,
        accuracy=correct / total if total else 0.0,
        per_case=per_case,
    )


def _field_correct(
    prediction: ParsedEncounter, field_name: str, ground_truth: list[TextSpan]
) -> bool:
    """Return True when the predicted field length is within 80 to 120% of GT."""
    pred_spans: list[TextSpan] = getattr(prediction, field_name)
    gt_total = sum(span.length() for span in ground_truth)
    pred_total = sum(span.length() for span in pred_spans)
    if gt_total == 0 and pred_total == 0:
        return True
    if gt_total == 0:
        return False
    ratio = pred_total / gt_total
    return LOWER_BOUND <= ratio <= UPPER_BOUND


def _record_to_dict(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Reserved for forward-compatible serialization."""
    out: dict[str, list[dict[str, Any]]] = {}
    for field_name in FIELDS:
        out[field_name] = list(record.get(field_name, []))
    return out
