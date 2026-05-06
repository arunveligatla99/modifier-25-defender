#!/usr/bin/env python3
"""Em-dash CI gate.

Constitution coding standard CS-3 (with the Q1 option C scope captured in
``specs/001-modifier-25-defender/research.md`` R10) prohibits the em-dash
character (U+2014) in curated text. Curated text means files authored by humans
or by agents during development. LLM-generated runtime content is out of scope
because forcing post-processing to strip em-dashes from cited spans risks
breaking citation fidelity.

Scope (in):

- ``app/**``
- ``eval/**`` (excluding ``eval/.cache/**``)
- ``ui/src/**``
- ``docs/**``
- ``specs/**``
- ``prompts/**``
- ``tests/**`` (text fixtures)
- ``scripts/**``
- top-level ``*.md``
- ``Makefile``, ``pyproject.toml``, ``.env.example``

Scope (out):

- ``data/synthetic/encounters/**`` (LLM-generated fixtures)
- ``eval/.cache/**`` (gitignored cache)
- ``eval/reports/**`` (generated reports)
- any path containing ``runtime-output`` or matching ``*.generated.*``
- binary files (detected by null-byte check)

Exit code 0 on clean; 1 on any em-dash hit, with file:line output.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Use the unicode escape so this script itself does not contain a literal
# U+2014 character (which would self-trigger the gate).
EM_DASH = "\u2014"

INCLUDE_PREFIXES: tuple[str, ...] = (
    "app/",
    "eval/",
    "ui/src/",
    "docs/",
    "specs/",
    "prompts/",
    "tests/",
    "scripts/",
)

EXCLUDE_PREFIXES: tuple[str, ...] = (
    "data/synthetic/encounters/",
    "eval/.cache/",
    "eval/reports/",
)

INCLUDE_TOP_LEVEL_NAMES: frozenset[str] = frozenset(
    {
        "Makefile",
        "pyproject.toml",
        ".env.example",
    }
)

INCLUDE_SUFFIXES: tuple[str, ...] = (".md",)


def _is_in_scope(rel_path: Path) -> bool:
    """Return True if ``rel_path`` is in scope for the em-dash check."""
    posix = rel_path.as_posix()

    for excluded in EXCLUDE_PREFIXES:
        if posix.startswith(excluded):
            return False

    if "runtime-output" in posix or ".generated." in posix:
        return False

    for prefix in INCLUDE_PREFIXES:
        if posix.startswith(prefix):
            return True

    if rel_path.name in INCLUDE_TOP_LEVEL_NAMES:
        return True

    if rel_path.parent == Path(".") and any(posix.endswith(s) for s in INCLUDE_SUFFIXES):
        return True

    return False


def _is_binary(path: Path) -> bool:
    """Quick null-byte heuristic for binary detection."""
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def main() -> int:
    """Walk the repository, scan in-scope files for U+2014, exit nonzero on any hit."""
    root = Path(".").resolve()
    hits: list[tuple[str, int, str]] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in {".git", "node_modules", ".venv", "dist", "build"}:
            continue
        if not _is_in_scope(rel):
            continue
        if _is_binary(path):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            if EM_DASH in line:
                hits.append((rel.as_posix(), lineno, line.rstrip()))

    if hits:
        sys.stderr.write(
            f"em-dash gate: found {len(hits)} occurrence(s) of U+2014 in curated text.\n"
            "Replace with comma, period, colon, parentheses, or rephrase.\n"
            "Constitution CS-3 (research.md R10) is non-negotiable.\n\n"
        )
        for path, lineno, line in hits:
            sys.stderr.write(f"{path}:{lineno}: {line}\n")
        return 1

    print("em-dash gate: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
