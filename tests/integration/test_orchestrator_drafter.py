"""Integration test for the orchestrator + drafter path (T203).

Exercises a WEAK overall encounter where the drafter is invoked and the
guard verifies its policy citations against an injected ``policy_text_index``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from app.agents.analyzer import AnalyzerAgent
from app.agents.compliance_guard import ComplianceGuard, NLIStub
from app.agents.drafter import DrafterAgent
from app.agents.orchestrator import orchestrate_request
from app.agents.parser import ParserAgent
from app.llm.openai_client import LLMResponse
from app.schemas.api import DefenderRequest

pytestmark = pytest.mark.integration


class FakeLLM:
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
    def search(self, query: str) -> Any:
        @dataclass
        class _R:
            query: str
            chunks: list[Any]

        return _R(query=query, chunks=[])


def test_weak_path_invokes_drafter_and_passes() -> None:
    note = "CC: ingrown toenail.\nHPI: ...\nExam: ...\nMDM: ...\nProcedure: ..."

    parser_response = json.dumps(
        {
            "cc": [{"text": "ingrown toenail", "start_char": 4, "end_char": 19}],
            "hpi": [],
            "exam_findings": [],
            "mdm": [],
            "procedure_note": [],
            "ambiguous_segments": [],
        }
    )

    def criterion(verdict: str) -> str:
        return json.dumps(
            {
                "verdict": verdict,
                "confidence": 0.9,
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

    drafter_response = json.dumps(
        {
            "remediations": [
                {
                    "criterion": "independent_mdm",
                    "suggested_addition": (
                        "Document an independent decision with risks, data, and management."
                    ),
                    "motivation": [
                        {
                            "source_type": "policy",
                            "span": {
                                "text": "policy text",
                                "start_char": 0,
                                "end_char": 11,
                            },
                            "policy_id": "policy-1",
                            "rationale": "policy supports the suggestion",
                        }
                    ],
                }
            ]
        }
    )

    llm = FakeLLM(
        responses=[
            parser_response,
            criterion("PASS"),
            criterion("PASS"),
            criterion("WEAK"),  # independent_mdm WEAK -> overall WEAK
            criterion("PASS"),
            drafter_response,
        ]
    )

    parser = ParserAgent(client=llm)
    retriever = FakeRetriever()
    analyzer = AnalyzerAgent(client=llm, retriever=retriever)
    drafter = DrafterAgent(client=llm, retriever=retriever)
    guard = ComplianceGuard(verifier=NLIStub(default=0.99))

    response = orchestrate_request(
        DefenderRequest(
            encounter_id="enc-int-002",
            note_text=note,
            em_code="99213",
            procedure_code="11721",
            modifier_25_attached=True,
            site="L",
        ),
        parser=parser,
        analyzer=analyzer,
        guard=guard,
        policy_text_index={"policy-1": "policy text passage"},
        drafter=drafter,
    )
    assert response.compliance_status == "PASSED"
    assert response.assessment is not None
    assert response.assessment.overall == "WEAK"
    assert len(response.remediations) == 1
    assert response.remediations[0].criterion == "independent_mdm"
    # 1 parser + 4 analyzer + 1 drafter
    assert llm.calls == 6
