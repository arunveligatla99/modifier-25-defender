"""Retrieval eval harness (T119).

Computes retrieval recall@5 against ``data/retrieval_eval/questions.jsonl``.
The threshold for AC-002-3 (recall@5 >= 0.85) is enforced by
:mod:`eval.check_gates`, not by this harness directly.
"""

from eval.retrieval.recall_at_5 import RecallReport, evaluate_recall_at_5

__all__ = ["RecallReport", "evaluate_recall_at_5"]
