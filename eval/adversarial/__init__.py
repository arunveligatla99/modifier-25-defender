"""Compliance Guard adversarial harnesses (T136, T137).

The adversarial recall harness verifies the Compliance Guard catches
hand-crafted hallucinated claims (AC-005-2 requires recall=1.00). The
false-positive harness measures how often the Guard incorrectly flags
ground-truth-correct claims (AC-005-3 requires fp <= 0.10).
"""

from eval.adversarial.false_positive import (
    FalsePositiveReport,
    evaluate_false_positive_rate,
)
from eval.adversarial.recall import AdversarialReport, evaluate_adversarial_recall

__all__ = [
    "AdversarialReport",
    "FalsePositiveReport",
    "evaluate_adversarial_recall",
    "evaluate_false_positive_rate",
]
