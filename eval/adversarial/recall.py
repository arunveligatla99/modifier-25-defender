"""Adversarial recall harness for the Compliance Guard (T136 / AC-005-2).

For each entry in ``data/adversarial/claims.jsonl``, runs the configured
NLI verifier on ``(premise, hypothesis)`` and asserts the entailment
probability is below the threshold. Recall is the fraction of fake claims
the guard correctly flagged as not-entailed. AC-005-2 requires 1.00.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.agents.compliance_guard.agent import NLI_THRESHOLD
from app.agents.compliance_guard.nli import NLIVerifier

logger = logging.getLogger(__name__)

DEFAULT_ADVERSARIAL_PATH = Path("data/adversarial/claims.jsonl")


@dataclass(frozen=True)
class AdversarialClaim:
    """One adversarial entry."""

    claim_id: str
    premise: str
    hypothesis: str
    criterion: str


@dataclass(frozen=True)
class AdversarialReport:
    """Output of the adversarial recall harness.

    Attributes:
        total: Number of fake claims evaluated.
        caught: Number the guard flagged below the threshold.
        recall: ``caught / total`` (AC-005-2 must equal 1.00).
        per_claim: Per-claim caught/missed flag.
    """

    total: int
    caught: int
    recall: float
    per_claim: dict[str, bool] = field(default_factory=dict)


def load_adversarial_set(path: Path = DEFAULT_ADVERSARIAL_PATH) -> list[AdversarialClaim]:
    """Load the adversarial claim set."""
    if not path.exists():
        return []
    entries: list[AdversarialClaim] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        entries.append(
            AdversarialClaim(
                claim_id=record["claim_id"],
                premise=record["premise"],
                hypothesis=record["hypothesis"],
                criterion=record.get("criterion", ""),
            )
        )
    return entries


def evaluate_adversarial_recall(
    verifier: NLIVerifier,
    claims: Iterable[AdversarialClaim] | None = None,
    *,
    threshold: float = NLI_THRESHOLD,
    path: Path = DEFAULT_ADVERSARIAL_PATH,
) -> AdversarialReport:
    """Compute recall on the adversarial set.

    Args:
        verifier: Any verifier matching :class:`NLIVerifier`.
        claims: Optional explicit claim list (defaults to loading from ``path``).
        threshold: Entailment threshold; values below count as "caught".
        path: Path to the adversarial JSONL file.

    Returns:
        An :class:`AdversarialReport` summarizing per-claim and aggregate.
    """
    items = list(claims) if claims is not None else load_adversarial_set(path)
    if not items:
        return AdversarialReport(0, 0, 0.0, per_claim={})

    per_claim: dict[str, bool] = {}
    caught = 0
    for item in items:
        score = verifier.entailment_probability(item.premise, item.hypothesis)
        is_caught = score < threshold
        per_claim[item.claim_id] = is_caught
        if is_caught:
            caught += 1
    total = len(items)
    return AdversarialReport(
        total=total,
        caught=caught,
        recall=caught / total if total else 0.0,
        per_claim=per_claim,
    )
