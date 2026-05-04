"""RAGAS faithfulness harness (T130, AC-004-5).

For each encounter in the synthetic test split, builds a multi-statement
answer from the analyzer's per-criterion outputs and scores it with
``ragas.metrics.Faithfulness`` against the retrieval contexts that fed
the analyzer. Surfaces ``analyzer.faithfulness`` (mean across encounters)
plus a per-encounter breakdown.
"""

from eval.faithfulness.ragas_runner import (
    FaithfulnessReport,
    evaluate_faithfulness,
)

__all__ = ["FaithfulnessReport", "evaluate_faithfulness"]
