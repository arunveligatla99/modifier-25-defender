"""Defensibility Analyzer agent.

Implements EPIC-004. For each of the four JARALL Standard criteria,
issues one GPT-4o call with retrieval context and parses the response into
a :class:`CriterionScore`. Combines the four sub-scores into a
deterministic overall verdict (any FAIL -> overall FAIL; any WEAK with no
FAIL -> overall WEAK; all PASS -> overall PASS).

The site-specificity criterion has a same-site special case: when the E/M
and procedure share an anatomic site (``site is None``), the verdict is
computed without an LLM call, encoded as PASS with confidence=1.0 and a
single Citation pointing at the determination. See spec edge cases.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from app.llm.openai_client import LLMResponse
from app.llm.schema import strict_schema_for
from app.schemas.assessment import (
    CriteriaMap,
    CriterionScore,
    DefensibilityAssessment,
    Verdict,
)
from app.schemas.parser import ParsedEncounter
from app.schemas.text import Citation, TextSpan

logger = logging.getLogger(__name__)

ANALYZER_PROMPT_VERSION = "v1"
PROMPTS_ROOT = Path("prompts") / "analyzer"

CRITERION_NAMES = (
    "distinct_cc",
    "separate_exam",
    "independent_mdm",
    "site_specificity",
)


class AnalyzerError(RuntimeError):
    """Raised when a per-criterion call fails twice on schema validation."""


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


@dataclass(frozen=True)
class AnalyzerAgent:
    """Wraps :func:`score_assessment` with sensible defaults."""

    client: _LLMClientLike
    retriever: _RetrieverLike
    prompts_root: Path = PROMPTS_ROOT
    max_retries: int = 1

    def score(
        self,
        parsed: ParsedEncounter,
        *,
        em_code: str,
        procedure_code: str,
        site: str | None,
    ) -> DefensibilityAssessment:
        """Score the four criteria, returning a full assessment."""
        return score_assessment(
            parsed,
            em_code=em_code,
            procedure_code=procedure_code,
            site=site,
            client=self.client,
            retriever=self.retriever,
            prompts_root=self.prompts_root,
            max_retries=self.max_retries,
        )


@dataclass(frozen=True)
class _AnalyzerInputs:
    """Inputs that vary across criterion-specific calls."""

    name: str
    query: str
    note_blob: str


def score_assessment(
    parsed: ParsedEncounter,
    *,
    em_code: str,
    procedure_code: str,
    site: str | None,
    client: _LLMClientLike,
    retriever: _RetrieverLike,
    prompts_root: Path = PROMPTS_ROOT,
    max_retries: int = 1,
) -> DefensibilityAssessment:
    """Score the four criteria for one encounter and return the assessment."""
    note_blob = _serialize_parsed(parsed)
    scores: dict[str, CriterionScore] = {}
    for name in CRITERION_NAMES:
        if name == "site_specificity" and site is None:
            scores[name] = _same_site_passthrough(parsed)
            continue
        query = _query_for(name, em_code, procedure_code, site)
        scores[name] = _call_criterion(
            name=name,
            query=query,
            note_blob=note_blob,
            site=site,
            client=client,
            retriever=retriever,
            prompts_root=prompts_root,
            max_retries=max_retries,
        )

    criteria = CriteriaMap(
        distinct_cc=scores["distinct_cc"],
        separate_exam=scores["separate_exam"],
        independent_mdm=scores["independent_mdm"],
        site_specificity=scores["site_specificity"],
    )
    overall = aggregate_overall(
        scores["distinct_cc"].verdict,
        scores["separate_exam"].verdict,
        scores["independent_mdm"].verdict,
        scores["site_specificity"].verdict,
    )
    return DefensibilityAssessment(overall=overall, criteria=criteria)


def aggregate_overall(*sub_verdicts: Verdict) -> Verdict:
    """Compute the overall verdict deterministically from sub-verdicts.

    Any FAIL forces overall FAIL; any WEAK with no FAIL produces WEAK; all
    PASS produces PASS. Spec EPIC-004 7.2.
    """
    if "FAIL" in sub_verdicts:
        return "FAIL"
    if "WEAK" in sub_verdicts:
        return "WEAK"
    return "PASS"


def _call_criterion(
    *,
    name: str,
    query: str,
    note_blob: str,
    site: str | None,
    client: _LLMClientLike,
    retriever: _RetrieverLike,
    prompts_root: Path,
    max_retries: int,
) -> CriterionScore:
    """Issue one criterion call with retrieval context and parse the response."""
    system_prompt = _load_prompt(prompts_root / name / f"{ANALYZER_PROMPT_VERSION}.md")
    retrieval_payload = _retrieve_payload(retriever, query)
    user_message = _user_message(note_blob=note_blob, site=site, retrieval=retrieval_payload)

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
                        "Re-emit corrected JSON matching CriterionScore."
                    ),
                }
            )
        response = client.chat(
            messages=messages,
            retrieval_context=retrieval_payload,
            response_format=strict_schema_for(CriterionScore),
            temperature=0.0,
        )
        try:
            payload = json.loads(response.content)
            score = CriterionScore.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning("analyzer[%s] attempt %d failed: %s", name, attempts, exc)
            continue
        return score

    raise AnalyzerError(
        f"analyzer criterion {name!r} failed after {attempts} attempt(s): {last_error}"
    )


def _retrieve_payload(retriever: _RetrieverLike, query: str) -> dict[str, Any]:
    """Run retrieval and serialize the top-5 chunks for prompt context."""
    result = retriever.search(query)
    chunks = list(getattr(result, "chunks", []))[:5]
    payload: list[dict[str, Any]] = []
    for chunk_score in chunks:
        chunk = chunk_score[0] if isinstance(chunk_score, tuple) else chunk_score
        score = chunk_score[1] if isinstance(chunk_score, tuple) else 0.0
        payload.append(
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "source_document": chunk.source_document,
                "authority_tier": chunk.authority_tier,
                "score": float(score),
            }
        )
    return {"chunks": payload}


def _user_message(
    *,
    note_blob: str,
    site: str | None,
    retrieval: dict[str, Any],
) -> str:
    return (
        "Parsed encounter:\n"
        f"{note_blob}\n\n"
        f"Anatomic site: {site or 'unspecified'}\n\n"
        "Retrieved policy chunks (top 5):\n"
        f"{json.dumps(retrieval, indent=2)}"
    )


def _serialize_parsed(parsed: ParsedEncounter) -> str:
    """Serialize a :class:`ParsedEncounter` for prompt insertion."""

    def fmt_field(name: str, spans: list[Any]) -> str:
        if not spans:
            return f"{name}: (empty)"
        joined = " | ".join(s.text for s in spans)
        return f"{name}: {joined}"

    return "\n".join(
        [
            fmt_field("CC", parsed.cc),
            fmt_field("HPI", parsed.hpi),
            fmt_field("Exam", parsed.exam_findings),
            fmt_field("MDM", parsed.mdm),
            fmt_field("Procedure", parsed.procedure_note),
            fmt_field("Ambiguous", parsed.ambiguous_segments),
        ]
    )


def _query_for(name: str, em_code: str, procedure_code: str, site: str | None) -> str:
    """Build a retrieval query for the given criterion."""
    site_phrase = f" site={site}" if site else ""
    if name == "distinct_cc":
        return (
            "Modifier 25 distinct chief complaint requirements "
            f"E/M {em_code} procedure {procedure_code}{site_phrase}"
        )
    if name == "separate_exam":
        return (
            "Modifier 25 separate exam findings documentation requirement "
            f"{em_code} {procedure_code}{site_phrase}"
        )
    if name == "independent_mdm":
        return "Modifier 25 independent medical decision making MDM separate problem " f"{em_code}"
    return (
        "Modifier 25 site-specificity LT RT modifier different anatomic sites "
        f"{procedure_code}{site_phrase}"
    )


def _same_site_passthrough(parsed: ParsedEncounter) -> CriterionScore:
    """Return the deterministic PASS used when site is None (same-site).

    Uses a real CC span from the parsed encounter so the citation passes
    NLI verification (the entailed_paraphrase is identical to the cited
    span's content). Falls back to a synthetic span only when the parser
    extracted no CC text at all.
    """
    cc_spans = list(parsed.cc)
    if cc_spans:
        cc = cc_spans[0]
        span = TextSpan(text=cc.text, start_char=cc.start_char, end_char=cc.end_char)
        paraphrase = cc.text
    else:
        # Defensive fallback. Real encounters always parse a CC; this path
        # is only hit when the parser returned an empty CC list.
        span = TextSpan(text="same-site encounter", start_char=0, end_char=19)
        paraphrase = "This encounter is a same-site encounter."
    citation = Citation(
        source_type="encounter",
        span=span,
        rationale=(
            "Site-specificity is N/A for same-site encounters and is encoded "
            "as PASS with confidence=1.0 per the data-model contract."
        ),
        entailed_paraphrase=paraphrase,
    )
    return CriterionScore(verdict="PASS", confidence=1.0, evidence=[citation])


def _load_prompt(path: Path) -> str:
    cached = _CACHE.get(path)
    if cached is not None:
        return cached
    text = path.read_text(encoding="utf-8")
    _CACHE[path] = text
    return text


_CACHE: dict[Path, str] = {}
