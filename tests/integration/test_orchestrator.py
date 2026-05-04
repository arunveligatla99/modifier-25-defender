"""Integration tests for the orchestrator (T150, T151).

Exercises the full parser -> analyzer -> compliance_guard pipeline against
stubbed agents. The tests cover the two user-visible terminal states:
PASSED and BLOCKED. They are tagged ``integration`` so the unit-test
fast-path (``make test-unit``) does not run them, but they live in the
default ``pytest`` invocation so CI catches regressions.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from app.agents.analyzer import AnalyzerAgent
from app.agents.compliance_guard import ComplianceGuard, NLIStub
from app.agents.orchestrator import orchestrate_request
from app.agents.parser import ParserAgent
from app.llm.openai_client import LLMResponse
from app.schemas.api import DefenderRequest

pytestmark = pytest.mark.integration


class FakeLLM:
    """LLM stub that returns canned responses by call index."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
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
        if not self._responses:
            raise AssertionError("FakeLLM ran out of canned responses")
        return LLMResponse(content=self._responses.pop(0), model=model or "gpt-4o")


class FakeRetriever:
    """Retriever returning an empty chunks list (synthesis works without context)."""

    def search(self, query: str) -> Any:
        from dataclasses import dataclass

        @dataclass
        class _Result:
            query: str
            chunks: list[Any]

        return _Result(query=query, chunks=[])


def _request(note: str) -> DefenderRequest:
    return DefenderRequest(
        encounter_id="enc-int-001",
        note_text=note,
        em_code="99213",
        procedure_code="11721",
        modifier_25_attached=True,
        site="L",
    )


def _parsed_for(note: str) -> str:
    """Build a JSON string a fake parser will return: every section gets one span."""
    return json.dumps(
        {
            "cc": [
                {"text": note[:10] or "x", "start_char": 0, "end_char": min(10, len(note)) or 1}
            ],
            "hpi": [],
            "exam_findings": [],
            "mdm": [],
            "procedure_note": [],
            "ambiguous_segments": [],
        }
    )


def _criterion_payload(verdict: str, span_text: str = "x") -> str:
    return json.dumps(
        {
            "verdict": verdict,
            "confidence": 0.9,
            "evidence": [
                {
                    "source_type": "encounter",
                    "span": {"text": span_text, "start_char": 0, "end_char": len(span_text)},
                    "policy_id": None,
                    "rationale": (
                        "Stub rationale that the NLI verifier will entail with the "
                        "default high score."
                    ),
                }
            ],
        }
    )


def test_pass_path_returns_passed_response() -> None:
    note = "CC: thick painful nails plus heel pain.\nHPI: weeks of symptoms.\nExam: ..."
    parser_responses = [_parsed_for(note)]
    analyzer_responses = [_criterion_payload("PASS") for _ in range(4)]
    llm = FakeLLM(responses=[*parser_responses, *analyzer_responses])

    parser = ParserAgent(client=llm)
    analyzer = AnalyzerAgent(client=llm, retriever=FakeRetriever())
    guard = ComplianceGuard(verifier=NLIStub(default=0.99))

    response = orchestrate_request(
        _request(note),
        parser=parser,
        analyzer=analyzer,
        guard=guard,
        policy_text_index={},
    )
    assert response.compliance_status == "PASSED"
    assert response.assessment is not None
    assert response.assessment.overall == "PASS"
    assert response.blocked_reasons is None
    assert response.trace_id.startswith("lf_t_local_")
    # 1 parser call + 4 analyzer calls = 5 total.
    assert llm.calls == 5


def test_blocked_path_strips_assessment() -> None:
    note = "CC: thick painful nails."
    parser_responses = [_parsed_for(note)]
    # Analyzer returns FAIL on independent_mdm and PASS elsewhere.
    analyzer_responses = [
        _criterion_payload("PASS"),  # distinct_cc
        _criterion_payload("PASS"),  # separate_exam
        _criterion_payload("FAIL"),  # independent_mdm
        _criterion_payload("PASS"),  # site_specificity
    ]
    llm = FakeLLM(responses=[*parser_responses, *analyzer_responses])

    parser = ParserAgent(client=llm)
    analyzer = AnalyzerAgent(client=llm, retriever=FakeRetriever())
    # Verifier returns 0.10 across the board so every citation fails.
    guard = ComplianceGuard(verifier=NLIStub(default=0.10))

    response = orchestrate_request(
        _request(note),
        parser=parser,
        analyzer=analyzer,
        guard=guard,
        policy_text_index={},
    )
    assert response.compliance_status == "BLOCKED"
    assert response.assessment is None
    assert response.remediations == []
    assert response.blocked_reasons is not None
    assert len(response.blocked_reasons) >= 1
    assert response.trace_id.startswith("lf_t_local_")
