"""Derive parser-eval ground truth from synthetic encounter notes.

The synthetic generator emits notes with regular section markers
(``CC: ...``, ``HPI: ...``, ``Exam: ...``, ``MDM: ...``,
``Procedure: ...``). Each section's body starts immediately after the
``"<label>: "`` prefix and runs to the next section marker (or the
verbose ``(End of note.)`` trailer, which is dropped).

This module scans those markers and emits a list of
:class:`eval.parser.field_accuracy.ParserEvalCase` objects suitable
for ``data/parser_eval/dev.jsonl``. AC-003-2 requires field-level
accuracy >= 0.90 against this ground truth.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from app.schemas.text import TextSpan

if TYPE_CHECKING:
    from eval.schemas import SyntheticEncounter

# (parser-field-name, marker-prefix-as-it-appears-in-the-note).
# Order matters: the body of each section runs to the next marker.
_SECTION_MARKERS: tuple[tuple[str, str], ...] = (
    ("cc", "CC: "),
    ("hpi", "HPI: "),
    ("exam_findings", "Exam: "),
    ("mdm", "MDM: "),
    ("procedure_note", "Procedure: "),
)

_VERBOSE_TRAILER = "(End of note.)"


def derive_spans(note_text: str) -> dict[str, list[TextSpan]]:
    """Return per-field ground-truth spans for one synthetic note.

    Args:
        note_text: The rendered encounter note.

    Returns:
        A dict mapping each parser field name (``cc``, ``hpi``,
        ``exam_findings``, ``mdm``, ``procedure_note``) to a list with a
        single :class:`TextSpan` covering that section's body. A field
        with no marker in the note maps to an empty list.
    """
    out: dict[str, list[TextSpan]] = {field: [] for field, _ in _SECTION_MARKERS}

    # Locate each marker in turn; record (field, body_start, marker_end).
    locations: list[tuple[str, int, int]] = []
    cursor = 0
    for field, marker in _SECTION_MARKERS:
        idx = note_text.find(marker, cursor)
        if idx == -1:
            continue
        body_start = idx + len(marker)
        locations.append((field, idx, body_start))
        cursor = body_start

    for i, (field, _, body_start) in enumerate(locations):
        # Body runs to the next marker's start (the "\nNext: " boundary).
        if i + 1 < len(locations):
            body_end = locations[i + 1][1]
        else:
            body_end = len(note_text)
        # Trim any trailing whitespace and the verbose "(End of note.)"
        # trailer so the eval-set spans match what a clean parser would
        # emit.
        body = note_text[body_start:body_end]
        body_end_trimmed = body_end - (len(body) - len(body.rstrip()))
        if body.rstrip().endswith(_VERBOSE_TRAILER):
            trimmed = body.rstrip()[: -len(_VERBOSE_TRAILER)].rstrip()
            body_end_trimmed = body_start + len(trimmed)
        text = note_text[body_start:body_end_trimmed]
        if not text:
            continue
        out[field] = [TextSpan(text=text, start_char=body_start, end_char=body_end_trimmed)]
    return out


def build_eval_set_records(
    encounters: Iterable[SyntheticEncounter],
) -> list[dict[str, object]]:
    """Build JSONL-ready records for the parser eval set.

    Args:
        encounters: Iterable of synthetic encounters (typically the test
            split).

    Returns:
        A list of dicts ready to be ``json.dumps``'d, one per encounter,
        with ``encounter_id``, ``note_text``, and one list-of-spans key
        per parser field.
    """
    records: list[dict[str, object]] = []
    for enc in encounters:
        spans = derive_spans(enc.note_text)
        record: dict[str, object] = {
            "encounter_id": enc.encounter_id,
            "note_text": enc.note_text,
        }
        for field, span_list in spans.items():
            record[field] = [
                {"text": s.text, "start_char": s.start_char, "end_char": s.end_char}
                for s in span_list
            ]
        records.append(record)
    return records


def write_eval_set(
    encounters: Iterable[SyntheticEncounter],
    out_path: Path,
) -> int:
    """Persist the parser eval set as JSONL.

    Args:
        encounters: Source encounters.
        out_path: Destination path; parent directories are created.

    Returns:
        Number of records written.
    """
    records = build_eval_set_records(encounters)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")
    return len(records)
