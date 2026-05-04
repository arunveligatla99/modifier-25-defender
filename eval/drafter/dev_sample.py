"""Emit the dev-split drafter sample for manual clinical review (T205).

For each dev-split encounter whose ground-truth overall verdict is not
PASS, run parser + analyzer + drafter and persist each suggestion with
the surrounding context (encounter note, criterion, motivation) to
``data/drafter_review/dev_sample.jsonl``. A reviewer scores the
samples in ``scores.jsonl`` with ``reasonable: true|false``.

The harness emits at least 20 suggestions per AC-006-4 by walking dev
encounters in deterministic order; if the dev split runs short, it
falls back to test-split encounters with non-PASS ground truth.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from app.schemas.assessment import DefensibilityAssessment
from app.schemas.parser import ParsedEncounter
from app.schemas.remediation import RemediationSuggestion

from eval.defensibility.accuracy import DEFAULT_ENCOUNTERS_DIR, DEFAULT_LABELS_PATH
from eval.schemas import SyntheticEncounter

logger = logging.getLogger(__name__)

DEFAULT_OUT_PATH = Path("data/drafter_review/dev_sample.jsonl")
DEFAULT_TARGET_COUNT = 20


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


class _DrafterLike(Protocol):
    def draft(
        self,
        parsed: ParsedEncounter,
        assessment: DefensibilityAssessment,
    ) -> list[RemediationSuggestion]: ...


def _load_split_encounters(
    splits: tuple[str, ...],
    labels_path: Path,
    encounters_dir: Path,
) -> list[SyntheticEncounter]:
    """Load encounters whose split is in ``splits``, in stable id order."""
    if not labels_path.exists():
        return []
    selected: list[tuple[str, str]] = []
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("split") in splits:
            selected.append((record["encounter_id"], record.get("split", "")))
    selected.sort()
    out: list[SyntheticEncounter] = []
    for eid, _ in selected:
        path = encounters_dir / f"{eid}.json"
        if not path.exists():
            continue
        out.append(SyntheticEncounter.model_validate_json(path.read_text(encoding="utf-8")))
    return out


def build_dev_sample(
    parser: _ParserLike,
    analyzer: _AnalyzerLike,
    drafter: _DrafterLike,
    *,
    target_count: int = DEFAULT_TARGET_COUNT,
    labels_path: Path = DEFAULT_LABELS_PATH,
    encounters_dir: Path = DEFAULT_ENCOUNTERS_DIR,
) -> list[dict[str, Any]]:
    """Generate review records, walking dev first then test as fallback."""
    candidates = _load_split_encounters(("dev", "test"), labels_path, encounters_dir)
    records: list[dict[str, Any]] = []
    for enc in candidates:
        if enc.ground_truth.overall == "PASS":
            continue
        try:
            parsed = parser.parse(enc.note_text)
            assessment = analyzer.score(
                parsed,
                em_code=enc.em_code,
                procedure_code=enc.procedure_code,
                site=enc.site,
            )
            suggestions = drafter.draft(parsed, assessment)
        except Exception as exc:
            logger.warning("dev-sample skipped %s: %s", enc.encounter_id, exc)
            continue
        for idx, sugg in enumerate(suggestions):
            records.append(
                {
                    "sample_id": f"{enc.encounter_id}::{sugg.criterion}::{idx}",
                    "encounter_id": enc.encounter_id,
                    "split": enc.split,
                    "criterion": sugg.criterion,
                    "ground_truth_overall": enc.ground_truth.overall,
                    "note_text": enc.note_text,
                    "suggested_addition": sugg.suggested_addition,
                    "motivation_citations": [
                        {"policy_id": c.policy_id, "span_text": c.span.text}
                        for c in sugg.motivation
                    ],
                }
            )
            if len(records) >= target_count:
                return records
    return records


def write_dev_sample(
    records: Iterable[dict[str, Any]],
    out_path: Path = DEFAULT_OUT_PATH,
) -> int:
    """Persist review records as JSONL; returns count written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
            written += 1
    return written
