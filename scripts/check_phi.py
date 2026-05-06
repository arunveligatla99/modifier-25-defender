#!/usr/bin/env python3
"""PHI denylist gate.

Constitution Principle IV prohibits real PHI in any commit, ever. This script
runs a conservative denylist check against the synthetic-data corpus and
fixtures, looking for markers that suggest a real-encounter leak.

Scope (in):

- ``data/synthetic/**``
- ``data/corpus/**``
- ``tests/**`` (fixtures)
- ``eval/**`` (eval inputs)

Scope (out):

- ``eval/.cache/**``
- ``eval/reports/**``
- binary files

Markers (denylist):

- Real DOB pattern (``MM/DD/YYYY`` or ``YYYY-MM-DD``) for dates of birth
  combined with a contextual word like ``DOB:`` or ``Date of Birth:``.
- Tagged-as-real names: any line containing the literal string ``REAL_NAME:``
  (used by reviewers to deliberately tag a leak before remediation).
- US Social Security Number pattern ``XXX-XX-XXXX``.
- Common medical record number prefixes such as ``MRN:`` followed by a value.
- Phone number pattern with US area code in parentheses.

Exit code 0 on clean; 1 on any hit.

Note: This script is intentionally conservative for v1. False positives are
fine; false negatives are the failure mode that violates Constitution
Principle IV. If a synthetic-data convention legitimately uses one of the
flagged patterns, add an explicit allowlist entry inside this script with a
PR description noting the rationale.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INCLUDE_PREFIXES: tuple[str, ...] = (
    "data/synthetic/",
    "data/corpus/",
    "tests/",
    "eval/",
)

EXCLUDE_PREFIXES: tuple[str, ...] = (
    "eval/.cache/",
    "eval/reports/",
)

PATTERNS: dict[str, re.Pattern[str]] = {
    "real_name_tag": re.compile(r"\bREAL_NAME\s*:"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "mrn": re.compile(r"\bMRN\s*:\s*[A-Z0-9-]{4,}", re.IGNORECASE),
    "dob_label_iso": re.compile(r"\b(?:DOB|Date of Birth)\s*:\s*\d{4}-\d{2}-\d{2}", re.IGNORECASE),
    "dob_label_us": re.compile(
        r"\b(?:DOB|Date of Birth)\s*:\s*\d{1,2}/\d{1,2}/\d{4}",
        re.IGNORECASE,
    ),
    "phone_us": re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}"),
}

ALLOWLIST: frozenset[str] = frozenset(
    {
        # Add specific file:line entries here with PR rationale, e.g.:
        # "data/synthetic/encounters/example_001.json:42",
    }
)


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def main() -> int:
    """Walk the synthetic and corpus paths, flag denylist matches."""
    root = Path(".").resolve()
    hits: list[tuple[str, int, str, str]] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        posix = rel.as_posix()
        if any(posix.startswith(x) for x in EXCLUDE_PREFIXES):
            continue
        if not any(posix.startswith(x) for x in INCLUDE_PREFIXES):
            continue
        if _is_binary(path):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            for marker, pattern in PATTERNS.items():
                if pattern.search(line):
                    key = f"{posix}:{lineno}"
                    if key in ALLOWLIST:
                        continue
                    hits.append((posix, lineno, marker, line.rstrip()))

    if hits:
        sys.stderr.write(
            f"PHI denylist gate: found {len(hits)} suspicious marker(s).\n"
            "Constitution Principle IV prohibits real PHI in any commit.\n\n"
        )
        for posix, lineno, marker, line in hits:
            sys.stderr.write(f"{posix}:{lineno} [{marker}]: {line}\n")
        return 1

    print("PHI denylist gate: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
