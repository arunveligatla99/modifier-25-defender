"""Unit tests for the Remediation Drafter agent (EPIC-006)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from app.agents.drafter import DrafterAgent, DrafterError, draft_remediations
from app.llm.openai_client import LLMResponse
from app.schemas.assessment import (
    CriteriaMap,
    CriterionScore,
    DefensibilityAssessment,
    Verdict,
)
from app.schemas.corpus import CorpusChunk
from app.schemas.parser import ParsedEncounter
from app.schemas.text import Citation, TextSpan


def _ev() -> Citation:
    return Citation(
        source_type="encounter",
        span=TextSpan(text="x", start_char=0, end_char=1),
        rationale="r",
        entailed_paraphrase="x",
    )


def _score(verdict: Verdict) -> CriterionScore:
    return CriterionScore(verdict=verdict, confidence=0.9, evidence=[_ev()])


def _assessment(
    cc: Verdict = "PASS",
    se: Verdict = "PASS",
    mdm: Verdict = "PASS",
    ss: Verdict = "PASS",
) -> DefensibilityAssessment:
    sub = (cc, se, mdm, ss)
    overall: Verdict
    if "FAIL" in sub:
        overall = "FAIL"
    elif "WEAK" in sub:
        overall = "WEAK"
    else:
        overall = "PASS"
    return DefensibilityAssessment(
        overall=overall,
        criteria=CriteriaMap(
            distinct_cc=_score(cc),
            separate_exam=_score(se),
            independent_mdm=_score(mdm),
            site_specificity=_score(ss),
        ),
    )


@dataclass
class _Result:
    query: str
    chunks: list[tuple[CorpusChunk, float]]


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, query: str) -> _Result:
        self.calls.append(query)
        return _Result(
            query=query,
            chunks=[
                (
                    CorpusChunk(
                        chunk_id=f"chunk-{len(self.calls)}",
                        text="policy text",
                        source_document="cms.txt",
                        authority_tier="CMS",
                    ),
                    0.9,
                )
            ],
        )


class SequencedClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        retrieval_context: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        if not self.responses:
            raise AssertionError("no canned responses left")
        return LLMResponse(content=self.responses.pop(0), model=model or "gpt-4o")


def _envelope(criteria: list[str]) -> str:
    return json.dumps(
        {
            "remediations": [
                {
                    "criterion": c,
                    "suggested_addition": f"Add {c} language",
                    "motivation": [
                        {
                            "source_type": "policy",
                            "span": {
                                "text": "policy span",
                                "start_char": 0,
                                "end_char": 11,
                            },
                            "policy_id": f"chunk-{i + 1}",
                            "rationale": "r",
                            "entailed_paraphrase": "p",
                        }
                    ],
                }
                for i, c in enumerate(criteria)
            ]
        }
    )


class TestDrafterAgent:
    def test_pass_overall_returns_empty_without_llm_call(self) -> None:
        client = SequencedClient(responses=[])
        agent = DrafterAgent(client=client, retriever=FakeRetriever())
        result = agent.draft(ParsedEncounter(), _assessment())
        assert result == []
        assert client.calls == 0

    def test_one_weak_criterion_yields_one_suggestion(self) -> None:
        client = SequencedClient(responses=[_envelope(["independent_mdm"])])
        retriever = FakeRetriever()
        result = draft_remediations(
            ParsedEncounter(),
            _assessment(mdm="WEAK"),
            client=client,
            retriever=retriever,
        )
        assert len(result) == 1
        assert result[0].criterion == "independent_mdm"
        assert client.calls == 1

    def test_multiple_weak_criteria_require_full_coverage(self) -> None:
        # First response covers only 2 of 3 weak criteria; expect retry.
        partial = _envelope(["independent_mdm", "distinct_cc"])
        full = _envelope(["independent_mdm", "distinct_cc", "separate_exam"])
        client = SequencedClient(responses=[partial, full])
        result = draft_remediations(
            ParsedEncounter(),
            _assessment(cc="FAIL", se="WEAK", mdm="FAIL"),
            client=client,
            retriever=FakeRetriever(),
        )
        assert client.calls == 2
        assert {r.criterion for r in result} == {
            "independent_mdm",
            "distinct_cc",
            "separate_exam",
        }

    def test_two_failures_raise(self) -> None:
        bad = json.dumps({"unexpected": "field"})
        client = SequencedClient(responses=[bad, bad])
        with pytest.raises(DrafterError):
            draft_remediations(
                ParsedEncounter(),
                _assessment(mdm="FAIL"),
                client=client,
                retriever=FakeRetriever(),
            )

    def test_each_suggestion_must_cite_at_least_one_policy(self) -> None:
        empty_motivation = json.dumps(
            {
                "remediations": [
                    {
                        "criterion": "independent_mdm",
                        "suggested_addition": "x",
                        "motivation": [],
                    }
                ]
            }
        )
        client = SequencedClient(responses=[empty_motivation, empty_motivation])
        with pytest.raises(DrafterError):
            draft_remediations(
                ParsedEncounter(),
                _assessment(mdm="WEAK"),
                client=client,
                retriever=FakeRetriever(),
            )
