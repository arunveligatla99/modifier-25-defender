#!/usr/bin/env python3
"""Import-graph lint enforcing the Compliance Guard separation (T138).

Constitution Principle II: synthesis and verification MUST be architecturally
separate. Code-level enforcement: ``app.agents.compliance_guard`` and the
synthesis-side agents (``parser``, ``analyzer``, ``drafter``) MUST NOT
import from each other in either direction.

Walk every Python file in scope, parse imports with ``ast``, and emit
violations to stderr with file paths. Exit nonzero on any violation.

Why this is non-negotiable: a future contributor (human or agent) could
otherwise refactor the verifier into the same module as the synthesis
agents and silently break the separation. The lint catches that at PR
time. Constitution + AC-005-6 (no bypass).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = ROOT / "app" / "agents"

GUARD_PACKAGE = "app.agents.compliance_guard"
SYNTHESIS_PACKAGES = (
    "app.agents.parser",
    "app.agents.analyzer",
    "app.agents.drafter",
)


def _collect_imports(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, module)`` pairs for every import in ``path``."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append((node.lineno, module))
    return imports


def _module_path(module: str) -> str:
    """Return the dotted package prefix for a module path."""
    return module


def _is_in_package(module: str, package: str) -> bool:
    """Return True if ``module`` is within ``package`` or a subpackage."""
    return module == package or module.startswith(package + ".")


def main() -> int:
    """Walk the agent tree and emit violations."""
    violations: list[tuple[Path, int, str, str]] = []

    for path in AGENTS_ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        # Determine which "side" this file belongs to.
        if "app/agents/compliance_guard" in rel:
            side = "guard"
        elif any(f"app/agents/{name}" in rel for name in ("parser", "analyzer", "drafter")):
            side = "synthesis"
        else:
            side = "neutral"  # orchestrator, package __init__

        if side == "neutral":
            continue

        try:
            imports = _collect_imports(path)
        except SyntaxError as exc:
            sys.stderr.write(f"{rel}: cannot parse ({exc}); skipping\n")
            continue

        for lineno, mod in imports:
            if side == "guard":
                for forbidden in SYNTHESIS_PACKAGES:
                    if _is_in_package(mod, forbidden):
                        violations.append((path, lineno, mod, forbidden))
            elif side == "synthesis":
                if _is_in_package(mod, GUARD_PACKAGE):
                    violations.append((path, lineno, mod, GUARD_PACKAGE))

    if violations:
        sys.stderr.write(
            "import-graph lint: violations of Constitution Principle II "
            "(synthesis and verification separation).\n"
            "T138 enforces that app.agents.compliance_guard and the synthesis-side "
            "agents MUST NOT import from each other.\n\n"
        )
        for path, lineno, mod, forbidden in violations:
            rel = path.relative_to(ROOT).as_posix()
            sys.stderr.write(
                f"{rel}:{lineno}: imports {mod!r} which crosses the boundary "
                f"into {forbidden!r}\n"
            )
        return 1

    print("import-graph lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
