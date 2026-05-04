"""Remediation Drafter agent.

Conditional agent: only runs when the analyzer's overall verdict is WEAK
or FAIL. Single GPT-4o call producing a list of :class:`RemediationSuggestion`
items. Each suggestion targets one weak criterion and cites at least one
policy chunk (AC-006-1, AC-006-2). Suggestions never modify the source
note (AC-006-3, Constitution Principle III).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.llm.openai_client import LLMResponse
from app.schemas.assessment import DefensibilityAssessment
from app.schemas.parser import ParsedEncounter
from app.schemas.remediation import CriterionName, RemediationSuggestion

logger = logging.getLogger(__name__)

DRAFTER_PROMPT_VERSION = "v1"
DRAFTER_PROMPT_PATH = Path("prompts") / "drafter" / f"{DRAFTER_PROMPT_VERSION}.md"

WEAK_VERDICTS = {"WEAK", "FAIL"}


class DrafterError(RuntimeError):
    """Raised when the drafter fails twice on schema validation."""


class _LLMClientLike(Protocol):
    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        retrieval_context: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse: ...


class _RetrieverLike(Protocol):
    def search(self, query: str) -> Any: ...


class _DrafterEnvelope(BaseModel):
    """Envelope schema produced by the drafter prompt."""

    remediations: list[RemediationSuggestion] = Field(default_factory=list)


@dataclass(frozen=True)
class DrafterAgent:
    """Wraps :func:`draft_remediations` with sensible defaults."""

    client: _LLMClientLike
    retriever: _RetrieverLike
    prompt_path: Path = DRAFTER_PROMPT_PATH
    max_retries: int = 1

    def draft(
        self,
        parsed: ParsedEncounter,
        assessment: DefensibilityAssessment,
    ) -> list[RemediationSuggestion]:
        """Return remediation suggestions for any WEAK or FAIL criterion.

        Args:
            parsed: Parsed encounter from the parser agent.
            assessment: Output of the analyzer agent.

        Returns:
            A list of :class:`RemediationSuggestion`. Empty when overall
            verdict is PASS.
        """
        if assessment.overall == "PASS":
            return []
        return draft_remediations(
            parsed,
            assessment,
            client=self.client,
            retriever=self.retriever,
            prompt_path=self.prompt_path,
            max_retries=self.max_retries,
        )


def draft_remediations(
    parsed: ParsedEncounter,
    assessment: DefensibilityAssessment,
    *,
    client: _LLMClientLike,
    retriever: _RetrieverLike,
    prompt_path: Path = DRAFTER_PROMPT_PATH,
    max_retries: int = 1,
) -> list[RemediationSuggestion]:
    """Functional implementation of :meth:`DrafterAgent.draft`."""
    weak_criteria = _weak_criteria(assessment)
    if not weak_criteria:
        return []

    system_prompt = prompt_path.read_text(encoding="utf-8")
    retrieval_payload = _retrieve_payload(retriever, weak_criteria)
    user_message = _user_message(
        parsed=parsed,
        assessment=assessment,
        weak_criteria=weak_criteria,
        retrieval=retrieval_payload,
    )

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    last_error: str | None = None
    attempts = 0
    while attempts <= max_retries:
        attempts += 1
        messages = list(base_messages)
        if last_error is not None:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous output failed schema validation:\n"
                        f"{last_error}\n"
                        "Re-emit corrected JSON matching the {remediations: [...]} envelope."
                    ),
                }
            )
        response = client.chat(
            messages=messages,
            retrieval_context=retrieval_payload,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        try:
            payload = json.loads(response.content)
            envelope = _DrafterEnvelope.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning("drafter attempt %d failed: %s", attempts, exc)
            continue

        # AC-006-1 enforcement: at least one suggestion per weak criterion.
        covered = {s.criterion for s in envelope.remediations}
        missing = weak_criteria - covered
        if missing:
            last_error = f"missing remediation suggestions for criteria: {sorted(missing)}"
            logger.warning("drafter attempt %d coverage gap: %s", attempts, missing)
            continue

        return envelope.remediations

    raise DrafterError(f"drafter failed after {attempts} attempt(s): {last_error}")


def _weak_criteria(assessment: DefensibilityAssessment) -> set[CriterionName]:
    """Return the subset of criterion names with WEAK or FAIL verdicts."""
    out: set[CriterionName] = set()
    for name, score in (
        ("distinct_cc", assessment.criteria.distinct_cc),
        ("separate_exam", assessment.criteria.separate_exam),
        ("independent_mdm", assessment.criteria.independent_mdm),
        ("site_specificity", assessment.criteria.site_specificity),
    ):
        if score.verdict in WEAK_VERDICTS:
            out.add(name)  # type: ignore[arg-type]
    return out


def _retrieve_payload(
    retriever: _RetrieverLike, weak_criteria: set[CriterionName]
) -> dict[str, Any]:
    """Run retrieval for each weak criterion and concatenate the top results."""
    queries = [_query_for(c) for c in sorted(weak_criteria)]
    chunks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in queries:
        result = retriever.search(q)
        for chunk_score in list(getattr(result, "chunks", []))[:5]:
            chunk = chunk_score[0] if isinstance(chunk_score, tuple) else chunk_score
            score = chunk_score[1] if isinstance(chunk_score, tuple) else 0.0
            cid = getattr(chunk, "chunk_id", None)
            if cid is None or cid in seen:
                continue
            seen.add(cid)
            chunks.append(
                {
                    "chunk_id": cid,
                    "text": chunk.text,
                    "source_document": chunk.source_document,
                    "authority_tier": chunk.authority_tier,
                    "score": float(score),
                }
            )
    return {"chunks": chunks}


def _query_for(criterion: CriterionName) -> str:
    if criterion == "distinct_cc":
        return "documentation language strengthening distinct chief complaint Modifier 25"
    if criterion == "separate_exam":
        return "documentation language separate exam findings non-procedure site Modifier 25"
    if criterion == "independent_mdm":
        return (
            "documentation language independent medical decision making "
            "separate problem Modifier 25"
        )
    return "documentation language site-specificity LT RT modifier coding"


def _user_message(
    *,
    parsed: ParsedEncounter,
    assessment: DefensibilityAssessment,
    weak_criteria: set[CriterionName],
    retrieval: dict[str, Any],
) -> str:
    return (
        "Parsed encounter:\n"
        f"{_serialize_parsed(parsed)}\n\n"
        f"Overall verdict: {assessment.overall}\n"
        f"Weak/Fail criteria: {sorted(weak_criteria)}\n\n"
        "Retrieved policy chunks (deduped across weak criteria):\n"
        f"{json.dumps(retrieval, indent=2)}"
    )


def _serialize_parsed(parsed: ParsedEncounter) -> str:
    def fmt(name: str, spans: list[Any]) -> str:
        if not spans:
            return f"{name}: (empty)"
        return f"{name}: " + " | ".join(s.text for s in spans)

    return "\n".join(
        [
            fmt("CC", parsed.cc),
            fmt("HPI", parsed.hpi),
            fmt("Exam", parsed.exam_findings),
            fmt("MDM", parsed.mdm),
            fmt("Procedure", parsed.procedure_note),
        ]
    )
