"""Tests for the adversarial recall and false-positive harnesses."""

from __future__ import annotations

from app.agents.compliance_guard import NLIStub
from eval.adversarial.false_positive import (
    CorrectClaim,
    evaluate_false_positive_rate,
)
from eval.adversarial.recall import (
    AdversarialClaim,
    evaluate_adversarial_recall,
    load_adversarial_set,
)


class TestAdversarialRecall:
    def test_recall_is_one_when_verifier_rejects_all_fakes(self) -> None:
        claims = [
            AdversarialClaim(
                claim_id=f"c{i}",
                premise="p",
                hypothesis="h",
                criterion="distinct_cc",
            )
            for i in range(5)
        ]
        verifier = NLIStub(default=0.10)
        report = evaluate_adversarial_recall(verifier, claims)
        assert report.total == 5
        assert report.caught == 5
        assert report.recall == 1.0

    def test_recall_drops_when_verifier_accepts_a_fake(self) -> None:
        claims = [
            AdversarialClaim(
                claim_id=f"c{i}",
                premise=f"p{i}",
                hypothesis="h",
                criterion="distinct_cc",
            )
            for i in range(5)
        ]
        # One pair is "verified" with a high score (the guard misses it).
        verifier = NLIStub(scores={("p2", "h"): 0.99}, default=0.10)
        report = evaluate_adversarial_recall(verifier, claims)
        assert report.caught == 4
        assert report.recall == 0.8
        assert report.per_claim["c2"] is False

    def test_loads_bundled_adversarial_set(self) -> None:
        items = load_adversarial_set()
        # Spec EPIC-005 5.2 specifies 20 hand-crafted hallucinated claims.
        assert len(items) == 20
        assert all(c.claim_id.startswith("adv") for c in items)


class TestFalsePositiveRate:
    def test_zero_when_verifier_passes_all(self) -> None:
        claims = [
            CorrectClaim(claim_id=f"c{i}", premise=f"p{i}", hypothesis="h") for i in range(10)
        ]
        verifier = NLIStub(default=0.99)
        report = evaluate_false_positive_rate(verifier, claims)
        assert report.total == 10
        assert report.false_positives == 0
        assert report.rate == 0.0

    def test_rate_when_verifier_flags_some_correct_claims(self) -> None:
        claims = [
            CorrectClaim(claim_id=f"c{i}", premise=f"p{i}", hypothesis="h") for i in range(10)
        ]
        # Two claims get "flagged" with low scores.
        verifier = NLIStub(
            scores={("p0", "h"): 0.10, ("p1", "h"): 0.10},
            default=0.99,
        )
        report = evaluate_false_positive_rate(verifier, claims)
        assert report.false_positives == 2
        assert report.rate == 0.2
