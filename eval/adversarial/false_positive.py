"""False-positive eval harness for the Compliance Guard (T137 / AC-005-3).

Runs the verifier on a list of ground-truth-correct claims and counts how
many it incorrectly flags below the threshold. AC-005-3 requires the rate
to be <= 0.10 on the 30-question retrieval eval set's correct claims.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from app.agents.compliance_guard.agent import NLI_THRESHOLD
from app.agents.compliance_guard.nli import NLIVerifier

DEFAULT_CORRECT_CLAIMS_PATH = Path("data/adversarial/correct_claims.jsonl")


@dataclass(frozen=True)
class CorrectClaim:
    """A ground-truth-correct claim used to measure false-positives."""

    claim_id: str
    premise: str
    hypothesis: str


@dataclass(frozen=True)
class FalsePositiveReport:
    """Output of the false-positive harness."""

    total: int
    false_positives: int
    rate: float
    per_claim: dict[str, bool] = field(default_factory=dict)


def load_correct_claims(path: Path = DEFAULT_CORRECT_CLAIMS_PATH) -> list[CorrectClaim]:
    """Load the ground-truth-correct claim set."""
    if not path.exists():
        return []
    out: list[CorrectClaim] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        out.append(
            CorrectClaim(
                claim_id=record["claim_id"],
                premise=record["premise"],
                hypothesis=record["hypothesis"],
            )
        )
    return out


def evaluate_false_positive_rate(
    verifier: NLIVerifier,
    claims: Iterable[CorrectClaim] | None = None,
    *,
    threshold: float = NLI_THRESHOLD,
    path: Path = DEFAULT_CORRECT_CLAIMS_PATH,
) -> FalsePositiveReport:
    """Compute false-positive rate on ground-truth-correct claims.

    Args:
        verifier: Any verifier matching :class:`NLIVerifier`.
        claims: Optional explicit claim list (defaults to loading from ``path``).
        threshold: Entailment threshold.
        path: Path to the correct-claims JSONL file.

    Returns:
        A :class:`FalsePositiveReport`.
    """
    items = list(claims) if claims is not None else load_correct_claims(path)
    if not items:
        return FalsePositiveReport(0, 0, 0.0, per_claim={})

    per_claim: dict[str, bool] = {}
    fps = 0
    for item in items:
        score = verifier.entailment_probability(item.premise, item.hypothesis)
        flagged = score < threshold
        per_claim[item.claim_id] = flagged
        if flagged:
            fps += 1
    total = len(items)
    return FalsePositiveReport(
        total=total,
        false_positives=fps,
        rate=fps / total if total else 0.0,
        per_claim=per_claim,
    )
