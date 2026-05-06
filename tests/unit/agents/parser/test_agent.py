"""Unit tests for the Documentation Parser agent."""

from __future__ import annotations

import json
from typing import Any

import pytest
from app.agents.parser import ParserError, parse_encounter
from app.llm.openai_client import LLMResponse


class FakeClient:
    """Stub LLM client that returns canned responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.last_messages: list[dict[str, str]] | None = None

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
        self.last_messages = messages
        if not self.responses:
            raise AssertionError("FakeClient: ran out of canned responses")
        content = self.responses.pop(0)
        return LLMResponse(content=content, model=model or "gpt-4o")


def _valid_response(note: str) -> str:
    """Return a JSON ParsedEncounter that aligns with ``note``."""
    cc_text = note.split("\n")[0].removeprefix("CC: ")
    cc_start = note.index(cc_text)
    cc_end = cc_start + len(cc_text)
    return json.dumps(
        {
            "cc": [{"text": cc_text, "start_char": cc_start, "end_char": cc_end}],
            "hpi": [],
            "exam_findings": [],
            "mdm": [],
            "procedure_note": [],
            "ambiguous_segments": [],
        }
    )


class TestParseEncounter:
    def test_happy_path_no_retry(self) -> None:
        note = "CC: thick painful nails\nHPI: ..."
        client = FakeClient(responses=[_valid_response(note)])
        parsed = parse_encounter(note, client=client)
        assert client.calls == 1
        assert parsed.cc[0].text == "thick painful nails"

    def test_retry_on_schema_failure_then_succeeds(self) -> None:
        note = "CC: ingrown toenail\nHPI: ..."
        bad = json.dumps({"unexpected": "field"})  # missing required schema
        client = FakeClient(responses=[bad, _valid_response(note)])
        parsed = parse_encounter(note, client=client, max_retries=1)
        assert client.calls == 2
        assert parsed.cc[0].text == "ingrown toenail"

    def test_two_failures_raise_parser_error(self) -> None:
        note = "CC: heel pain\nHPI: ..."
        bad = json.dumps({"unexpected": "field"})
        client = FakeClient(responses=[bad, bad])
        with pytest.raises(ParserError):
            parse_encounter(note, client=client, max_retries=1)

    def test_invalid_json_treated_as_validation_failure(self) -> None:
        note = "CC: callus pain\nHPI: ..."
        client = FakeClient(responses=["not json", _valid_response(note)])
        parsed = parse_encounter(note, client=client, max_retries=1)
        assert client.calls == 2
        assert parsed.cc[0].text == "callus pain"

    def test_retry_message_includes_validation_error(self) -> None:
        note = "CC: hallux pain\nHPI: ..."
        bad = json.dumps({"cc": "should be a list"})  # type-wrong field
        client = FakeClient(responses=[bad, _valid_response(note)])
        parse_encounter(note, client=client, max_retries=1)
        assert client.last_messages is not None
        # Last message should contain the corrective prompt.
        last = client.last_messages[-1]["content"]
        assert "schema validation" in last

    def test_ambiguous_segments_round_trip(self) -> None:
        note = (
            "CC: ankle pain\n"
            "HPI: weeks of pain.\n"
            "AMBIG: this line is ambiguous and should be marked.\n"
            "Exam: nothing else."
        )
        amb_text = "AMBIG: this line is ambiguous and should be marked."
        amb_start = note.index(amb_text)
        amb_end = amb_start + len(amb_text)
        canned = json.dumps(
            {
                "cc": [{"text": "ankle pain", "start_char": 4, "end_char": 14}],
                "hpi": [],
                "exam_findings": [],
                "mdm": [],
                "procedure_note": [],
                "ambiguous_segments": [
                    {"text": amb_text, "start_char": amb_start, "end_char": amb_end}
                ],
            }
        )
        client = FakeClient(responses=[canned])
        parsed = parse_encounter(note, client=client)
        assert len(parsed.ambiguous_segments) == 1
        assert parsed.ambiguous_segments[0].text == amb_text
