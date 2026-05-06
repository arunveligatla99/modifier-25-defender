"""Drafter clinical reasonableness harness (T205, AC-006-4).

Two pieces:

- :mod:`eval.drafter.dev_sample` regenerates the 20-suggestion dev-split
  sample to ``data/drafter_review/dev_sample.jsonl`` so a CPC-trained
  reviewer (or careful self-review) has a clean input to score.
- :mod:`eval.drafter.clinical_reasonableness` reads back the human
  review scores from ``data/drafter_review/scores.jsonl`` and computes
  the fraction marked ``reasonable``. Missing review file means the
  metric is 0.0 (gate fails intentionally).
"""

from eval.drafter.clinical_reasonableness import (
    ClinicalReasonablenessReport,
    evaluate_clinical_reasonableness,
)
from eval.drafter.dev_sample import build_dev_sample, write_dev_sample

__all__ = [
    "ClinicalReasonablenessReport",
    "build_dev_sample",
    "evaluate_clinical_reasonableness",
    "write_dev_sample",
]
