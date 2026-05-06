"""Tests for the NLIStub used by the Compliance Guard."""

from __future__ import annotations

from app.agents.compliance_guard import NLIStub


def test_default_is_returned_for_unmapped_pair() -> None:
    stub = NLIStub(default=0.42)
    assert stub.entailment_probability("a", "b") == 0.42


def test_explicit_pair_overrides_default() -> None:
    stub = NLIStub(scores={("p", "h"): 0.99}, default=0.10)
    assert stub.entailment_probability("p", "h") == 0.99
    assert stub.entailment_probability("p", "different") == 0.10


def test_calls_are_recorded() -> None:
    stub = NLIStub()
    stub.entailment_probability("p1", "h1")
    stub.entailment_probability("p2", "h2")
    assert stub.calls == [("p1", "h1"), ("p2", "h2")]
