"""Tests for the import-graph lint (T138).

Functional tests run the script against synthetic file trees in tmp_path
to verify it catches both forbidden import directions.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_imports.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_imports", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_imports"] = module
    spec.loader.exec_module(module)
    return module


def test_collect_imports_extracts_simple_and_from(tmp_path: Path) -> None:
    mod = _load_module()
    file = tmp_path / "x.py"
    file.write_text(
        "import os\n" "from app.agents.parser import agent\n" "from . import sibling\n",
        encoding="utf-8",
    )
    pairs = mod._collect_imports(file)
    modules = {m for _, m in pairs}
    assert "os" in modules
    assert "app.agents.parser" in modules


def test_is_in_package() -> None:
    mod = _load_module()
    assert mod._is_in_package("app.agents.parser", "app.agents.parser")
    assert mod._is_in_package("app.agents.parser.agent", "app.agents.parser")
    assert not mod._is_in_package("app.agents.parserx", "app.agents.parser")
    assert not mod._is_in_package("app.agents.analyzer", "app.agents.parser")


@pytest.mark.parametrize(
    "side, forbidden_import",
    [
        ("compliance_guard", "from app.agents.parser import agent"),
        ("compliance_guard", "from app.agents.analyzer.agent import score_assessment"),
        ("parser", "from app.agents.compliance_guard import nli"),
        ("analyzer", "import app.agents.compliance_guard"),
    ],
)
def test_lint_catches_violation(
    tmp_path: Path, side: str, forbidden_import: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_module()
    # Build a fake project tree under tmp_path that mirrors the parts of
    # app/agents/ the lint cares about.
    agents_root = tmp_path / "app" / "agents"
    target_dir = agents_root / side
    target_dir.mkdir(parents=True)
    (target_dir / "__init__.py").write_text("", encoding="utf-8")
    (target_dir / "module.py").write_text(forbidden_import + "\n", encoding="utf-8")
    # Also create empty siblings so the side detection logic has neighbors.
    for other in ("parser", "analyzer", "drafter", "compliance_guard"):
        (agents_root / other).mkdir(exist_ok=True)
        (agents_root / other / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "AGENTS_ROOT", agents_root)

    rc = mod.main()
    assert rc == 1


def test_lint_clean_on_empty_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module()
    agents_root = tmp_path / "app" / "agents"
    agents_root.mkdir(parents=True)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "AGENTS_ROOT", agents_root)
    assert mod.main() == 0


def test_lint_clean_on_real_repo() -> None:
    """The real repo MUST pass the import-graph lint."""
    mod = _load_module()
    assert mod.main() == 0
