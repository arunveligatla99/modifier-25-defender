"""Unit tests for the Defensibility Analyzer agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from app.agents.analyzer import AnalyzerError, aggregate_overall, score_assessment
from app.llm.openai_client import LLMResponse
from app.schemas.corpus import CorpusChunk
from app.schemas.parser import ParsedEncounter
from app.schemas.text import TextSpan


def _span(text: str, start: int, end: int) -> TextSpan:
    return TextSpan(text=text, start_char=start, end_char=end)


def _criterion_payload(verdict: str, conf: float = 0.9) -> str:
    return json.dumps(
        {
            "verdict": verdict,
            "confidence": conf,
            "evidence": [
                {
                    "source_type": "encounter",
                    "span": {"text": "x", "start_char": 0, "end_char": 1},
                    "policy_id": None,
                    "rationale": "stub",
                }
            ],
        }
    )


@dataclass
class _Result:
    query: str
    chunks: list[tuple[CorpusChunk, float]]


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._chunks = [
            (
                CorpusChunk(
                    chunk_id="cms|abc",
                    text="CMS guidance text",
                    source_document="cms.txt",
                    authority_tier="CMS",
                ),
                0.9,
            )
        ]

    def search(self, query: str) -> _Result:
        self.calls.append(query)
        return _Result(query=query, chunks=list(self._chunks))


class SequencedClient:
    """Returns canned responses keyed on call index across all criterion calls."""

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
            raise AssertionError("ran out of canned responses")
        return LLMResponse(content=self.responses.pop(0), model=model or "gpt-4o")


def _basic_parsed() -> ParsedEncounter:
    return ParsedEncounter(
        cc=[_span("thick painful nails plus heel pain", 0, 34)],
        hpi=[_span("HPI text", 36, 44)],
        exam_findings=[_span("Exam text", 46, 55)],
        mdm=[_span("MDM text", 57, 65)],
        procedure_note=[_span("Procedure text", 67, 81)],
    )


class TestAggregateOverall:
    def test_all_pass(self) -> None:
        assert aggregate_overall("PASS", "PASS", "PASS", "PASS") == "PASS"

    def test_any_fail_forces_fail(self) -> None:
        assert aggregate_overall("PASS", "FAIL", "PASS", "WEAK") == "FAIL"

    def test_any_weak_forces_weak(self) -> None:
        assert aggregate_overall("PASS", "WEAK", "PASS", "PASS") == "WEAK"


class TestScoreAssessment:
    def test_four_calls_when_site_provided(self) -> None:
        client = SequencedClient(
            responses=[
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
            ]
        )
        retriever = FakeRetriever()
        assessment = score_assessment(
            _basic_parsed(),
            em_code="99213",
            procedure_code="11721",
            site="L",
            client=client,
            retriever=retriever,
        )
        assert client.calls == 4
        assert len(retriever.calls) == 4
        assert assessment.overall == "PASS"

    def test_three_calls_when_site_is_none_same_site_special_case(self) -> None:
        client = SequencedClient(
            responses=[
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
            ]
        )
        retriever = FakeRetriever()
        assessment = score_assessment(
            _basic_parsed(),
            em_code="99213",
            procedure_code="11721",
            site=None,
            client=client,
            retriever=retriever,
        )
        assert client.calls == 3
        # site_specificity must be PASS with confidence 1.0
        assert assessment.criteria.site_specificity.verdict == "PASS"
        assert assessment.criteria.site_specificity.confidence == 1.0
        assert assessment.criteria.site_specificity.evidence[0].source_type == "encounter"

    def test_any_fail_forces_overall_fail(self) -> None:
        client = SequencedClient(
            responses=[
                _criterion_payload("FAIL"),
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
            ]
        )
        assessment = score_assessment(
            _basic_parsed(),
            em_code="99213",
            procedure_code="11721",
            site="L",
            client=client,
            retriever=FakeRetriever(),
        )
        assert assessment.overall == "FAIL"

    def test_retry_on_validation_then_succeeds(self) -> None:
        bad = json.dumps({"unexpected": "field"})
        client = SequencedClient(
            responses=[
                bad,
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
                _criterion_payload("PASS"),
            ]
        )
        assessment = score_assessment(
            _basic_parsed(),
            em_code="99213",
            procedure_code="11721",
            site="L",
            client=client,
            retriever=FakeRetriever(),
        )
        assert client.calls == 5
        assert assessment.overall == "PASS"

    def test_two_failures_raise_analyzer_error(self) -> None:
        bad = json.dumps({"unexpected": "field"})
        client = SequencedClient(responses=[bad, bad])
        with pytest.raises(AnalyzerError):
            score_assessment(
                _basic_parsed(),
                em_code="99213",
                procedure_code="11721",
                site="L",
                client=client,
                retriever=FakeRetriever(),
            )

    def test_evidence_must_be_non_empty_enforced_by_schema(self) -> None:
        empty = json.dumps(
            {
                "verdict": "PASS",
                "confidence": 0.5,
                "evidence": [],  # invalid per schema
            }
        )
        client = SequencedClient(responses=[empty, empty])
        with pytest.raises(AnalyzerError):
            score_assessment(
                _basic_parsed(),
                em_code="99213",
                procedure_code="11721",
                site="L",
                client=client,
                retriever=FakeRetriever(),
            )
