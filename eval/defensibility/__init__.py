"""Defensibility analyzer accuracy harness (T129).

Evaluates the analyzer agent against the synthetic test split. AC-004-2
requires overall verdict accuracy >= 0.85 (lenient: WEAK matches either
PASS or FAIL ground truth, only PASS-vs-FAIL confusions count). AC-004-3
requires per-criterion accuracy averaged across the 4 criteria >= 0.80.
"""

from eval.defensibility.accuracy import (
    DefensibilityAccuracyReport,
    evaluate_defensibility_accuracy,
)

__all__ = ["DefensibilityAccuracyReport", "evaluate_defensibility_accuracy"]
