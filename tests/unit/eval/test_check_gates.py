"""Unit tests for eval.check_gates (T307)."""

from __future__ import annotations

from pathlib import Path

import pytest
from eval.check_gates import (
    GateViolation,
    evaluate_thresholds,
    latest_report,
    load_thresholds,
    main,
)

THRESHOLDS = {
    "retrieval": {"recall_at_5": {"minimum": 0.85}},
    "compliance_guard": {
        "adversarial_recall": {"minimum": 1.0},
        "false_positive_rate": {"maximum": 0.10},
    },
}


class TestEvaluateThresholds:
    def test_clean_report_has_no_violations(self) -> None:
        report = {
            "retrieval": {"recall_at_5": 0.92},
            "compliance_guard": {
                "adversarial_recall": 1.0,
                "false_positive_rate": 0.05,
            },
        }
        assert evaluate_thresholds(report, THRESHOLDS) == []

    def test_minimum_violation(self) -> None:
        report = {
            "retrieval": {"recall_at_5": 0.50},
            "compliance_guard": {
                "adversarial_recall": 1.0,
                "false_positive_rate": 0.05,
            },
        }
        v = evaluate_thresholds(report, THRESHOLDS)
        assert len(v) == 1
        assert v[0].metric_path == "retrieval.recall_at_5"
        assert v[0].bound == "minimum"

    def test_maximum_violation(self) -> None:
        report = {
            "retrieval": {"recall_at_5": 0.99},
            "compliance_guard": {
                "adversarial_recall": 1.0,
                "false_positive_rate": 0.20,
            },
        }
        v = evaluate_thresholds(report, THRESHOLDS)
        assert len(v) == 1
        assert v[0].metric_path == "compliance_guard.false_positive_rate"
        assert v[0].bound == "maximum"

    def test_missing_metric_records_violation(self) -> None:
        report: dict = {"retrieval": {}, "compliance_guard": {}}
        v = evaluate_thresholds(report, THRESHOLDS)
        assert len(v) == 3
        assert {entry.bound for entry in v} == {"missing"}

    def test_render_includes_threshold_and_actual(self) -> None:
        v = GateViolation(
            metric_path="retrieval.recall_at_5",
            bound="minimum",
            threshold=0.85,
            actual=0.50,
        )
        rendered = v.render()
        assert "retrieval.recall_at_5" in rendered
        assert "0.85" in rendered
        assert "0.5" in rendered


class TestLoadThresholds:
    def test_loads_real_thresholds(self) -> None:
        # The repo's eval/thresholds.yaml must parse cleanly.
        thresholds = load_thresholds()
        for category in (
            "retrieval",
            "parser",
            "analyzer",
            "compliance_guard",
            "drafter",
            "end_to_end",
            "ui",
        ):
            assert category in thresholds


class TestLatestReport:
    def test_returns_none_on_empty_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "reports"
        d.mkdir()
        assert latest_report(d) is None

    def test_returns_lex_max(self, tmp_path: Path) -> None:
        d = tmp_path / "reports"
        d.mkdir()
        (d / "2026-01-01.json").write_text("{}", encoding="utf-8")
        (d / "2026-05-01.json").write_text("{}", encoding="utf-8")
        out = latest_report(d)
        assert out is not None
        assert out.name == "2026-05-01.json"


class TestMainCLI:
    def test_exits_with_2_when_no_report(self, tmp_path: Path) -> None:
        thresholds = tmp_path / "th.yaml"
        thresholds.write_text("retrieval:\n  recall_at_5:\n    minimum: 0.5\n", encoding="utf-8")
        rc = main(
            [
                "--thresholds",
                str(thresholds),
                "--report",
                str(tmp_path / "missing.json"),
            ]
        )
        assert rc == 2

    def test_exits_zero_when_clean(self, tmp_path: Path) -> None:
        thresholds = tmp_path / "th.yaml"
        thresholds.write_text("retrieval:\n  recall_at_5:\n    minimum: 0.5\n", encoding="utf-8")
        report = tmp_path / "report.json"
        report.write_text(
            '{"retrieval": {"recall_at_5": 0.95}}',
            encoding="utf-8",
        )
        assert main(["--thresholds", str(thresholds), "--report", str(report)]) == 0

    def test_exits_one_when_violation(self, tmp_path: Path) -> None:
        thresholds = tmp_path / "th.yaml"
        thresholds.write_text("retrieval:\n  recall_at_5:\n    minimum: 0.95\n", encoding="utf-8")
        report = tmp_path / "report.json"
        report.write_text(
            '{"retrieval": {"recall_at_5": 0.50}}',
            encoding="utf-8",
        )
        assert main(["--thresholds", str(thresholds), "--report", str(report)]) == 1


@pytest.mark.parametrize(
    "category",
    [
        "retrieval",
        "parser",
        "analyzer",
        "compliance_guard",
        "drafter",
        "end_to_end",
        "ui",
    ],
)
def test_real_thresholds_have_required_categories(category: str) -> None:
    """Sanity: the real thresholds file covers every spec category."""
    thresholds = load_thresholds()
    assert isinstance(thresholds.get(category), dict)
    assert thresholds[category]
