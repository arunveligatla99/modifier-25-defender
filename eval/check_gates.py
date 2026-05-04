"""Quality-gate checker for the eval harness output (T303 / AC-007-*).

Loads the latest report under ``eval/reports/`` (or a path passed via
``--report``) and compares each metric against the threshold defined in
``eval/thresholds.yaml``. Exits non-zero on any violation with a structured
error block per failing gate.

Constitution + AC-007-6: gates are not advisory. CI fails the PR on any
violation. Threshold changes require a separate PR with a rationale block
in the description (enforced by ``.github/workflows/ci.yml``).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS_PATH = Path("eval/thresholds.yaml")
DEFAULT_REPORTS_DIR = Path("eval/reports")


@dataclass(frozen=True)
class GateViolation:
    """One violated gate."""

    metric_path: str
    bound: str  # "minimum" or "maximum"
    threshold: float
    actual: float

    def render(self) -> str:
        """Format the violation for stderr."""
        op = ">=" if self.bound == "minimum" else "<="
        return (
            f"{self.metric_path}: actual={self.actual} violates {self.bound}={self.threshold} "
            f"(must be {op} {self.threshold})"
        )


def load_thresholds(path: Path = DEFAULT_THRESHOLDS_PATH) -> dict[str, Any]:
    """Load the threshold YAML."""
    if not path.exists():
        raise FileNotFoundError(f"thresholds file missing: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def latest_report(reports_dir: Path = DEFAULT_REPORTS_DIR) -> Path | None:
    """Return the most recent report file under ``reports_dir`` or None."""
    if not reports_dir.exists():
        return None
    candidates = sorted(reports_dir.glob("*.json"))
    return candidates[-1] if candidates else None


def evaluate_thresholds(report: dict[str, Any], thresholds: dict[str, Any]) -> list[GateViolation]:
    """Compare every threshold against the report and return violations."""
    violations: list[GateViolation] = []
    for category, metrics in thresholds.items():
        if not isinstance(metrics, dict):
            continue
        for metric_name, bounds in metrics.items():
            if not isinstance(bounds, dict):
                continue
            actual = _lookup(report, [category, metric_name])
            if actual is None:
                violations.append(
                    GateViolation(
                        metric_path=f"{category}.{metric_name}",
                        bound="missing",
                        threshold=float("nan"),
                        actual=float("nan"),
                    )
                )
                continue
            if "minimum" in bounds:
                minimum = float(bounds["minimum"])
                if float(actual) < minimum:
                    violations.append(
                        GateViolation(
                            metric_path=f"{category}.{metric_name}",
                            bound="minimum",
                            threshold=minimum,
                            actual=float(actual),
                        )
                    )
            if "maximum" in bounds:
                maximum = float(bounds["maximum"])
                if float(actual) > maximum:
                    violations.append(
                        GateViolation(
                            metric_path=f"{category}.{metric_name}",
                            bound="maximum",
                            threshold=maximum,
                            actual=float(actual),
                        )
                    )
    return violations


def _lookup(payload: dict[str, Any], path: list[str]) -> Any:
    """Return ``payload[path[0]][path[1]]...`` or None when any key is missing."""
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="eval.check_gates")
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=DEFAULT_THRESHOLDS_PATH,
        help="Path to the thresholds YAML.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to the report JSON (defaults to the latest under eval/reports/).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    thresholds = load_thresholds(args.thresholds)
    report_path = args.report or latest_report()
    if report_path is None:
        sys.stderr.write("no eval report found; run 'make eval' first or pass --report\n")
        return 2
    if not report_path.exists():
        sys.stderr.write(f"report not found: {report_path}\n")
        return 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    violations = evaluate_thresholds(report, thresholds)
    if violations:
        sys.stderr.write(f"eval gate FAILED: {len(violations)} violation(s) in {report_path}\n\n")
        for v in violations:
            sys.stderr.write(f"  {v.render()}\n")
        return 1
    print(f"eval gate PASSED: {report_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
