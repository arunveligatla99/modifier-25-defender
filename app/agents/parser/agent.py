"""Documentation Parser agent.

Wraps a single GPT-4o call with strict JSON-schema output, one retry on
schema failure (AC-003-4), and explicit ``ambiguous_segments`` surfacing
(AC-003-3). The retry feeds the Pydantic validation error back to the
model so it can correct itself.

The agent does not invoke the OpenAI SDK directly; it accepts a
:class:`CachedLLMClient` (production) or any object exposing the same
``chat`` signature (tests).
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
from app.schemas.parser import ParsedEncounter

logger = logging.getLogger(__name__)

PARSER_PROMPT_VERSION = "v1"
PARSER_PROMPT_PATH = Path("prompts") / "parser" / f"{PARSER_PROMPT_VERSION}.md"


class ParserError(RuntimeError):
    """Raised when the parser fails twice on schema validation (AC-003-4)."""


class _LLMClientLike(Protocol):
    """Subset of :class:`app.llm.openai_client.CachedLLMClient` we depend on."""

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        retrieval_context: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse: ...


@dataclass(frozen=True)
class ParserAgent:
    """Documentation Parser agent.

    Attributes:
        client: Cached LLM client (or test stub).
        prompt_path: Path to the prompt template; defaults to ``v1``.
        max_retries: Number of schema-validation retries before raising.
            v1 design AC-003-4 specifies exactly one retry.
        model: Optional OpenAI model override. Parser is structured
            extraction (no creative reasoning), so callers typically
            pass gpt-4o-mini to cut cost ~10x vs the default analyzer
            model.
    """

    client: _LLMClientLike
    prompt_path: Path = PARSER_PROMPT_PATH
    max_retries: int = 1
    model: str | None = None

    def parse(self, note_text: str) -> ParsedEncounter:
        """Parse the encounter note into a :class:`ParsedEncounter`.

        Args:
            note_text: Raw encounter text.

        Returns:
            A validated :class:`ParsedEncounter`.

        Raises:
            ParserError: If schema validation still fails after one retry.
        """
        return parse_encounter(
            note_text,
            client=self.client,
            prompt_path=self.prompt_path,
            max_retries=self.max_retries,
            model=self.model,
        )


def parse_encounter(
    note_text: str,
    *,
    client: _LLMClientLike,
    prompt_path: Path = PARSER_PROMPT_PATH,
    max_retries: int = 1,
    model: str | None = None,
) -> ParsedEncounter:
    """Functional entry point used by both :class:`ParserAgent` and the orchestrator.

    Args:
        note_text: Raw encounter text.
        client: Cached LLM client (or test stub).
        prompt_path: Path to the prompt template.
        max_retries: Number of validation retries before raising.
        model: Optional OpenAI model override; ``None`` uses the
            client's default. Callers typically pass
            ``settings.parser_model`` (gpt-4o-mini) here.

    Returns:
        A validated :class:`ParsedEncounter`.

    Raises:
        ParserError: If validation still fails after the retry budget.
    """
    system_prompt = _load_prompt(prompt_path)
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": note_text},
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
                        "Your previous output failed schema validation with this error:\n"
                        f"{last_error}\n"
                        "Re-emit a corrected JSON object that validates against ParsedEncounter."
                    ),
                }
            )
        response = client.chat(
            messages=messages,
            response_format=strict_schema_for(ParsedEncounter),
            temperature=0.0,
            model=model,
        )
        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError as exc:
            last_error = f"json decode error: {exc}"
            logger.warning("parser attempt %d: invalid JSON (%s)", attempts, exc)
            continue
        try:
            parsed = ParsedEncounter.model_validate(payload)
        except ValidationError as exc:
            last_error = exc.json()
            logger.warning("parser attempt %d: schema validation failed", attempts)
            continue
        return parsed

    raise ParserError(
        f"parser failed schema validation after {attempts} attempt(s); last error: {last_error}"
    )


def _load_prompt(path: Path) -> str:
    """Load the parser prompt from disk, with a small in-memory cache."""
    cached = _PROMPT_CACHE.get(path)
    if cached is not None:
        return cached
    text = path.read_text(encoding="utf-8")
    _PROMPT_CACHE[path] = text
    return text


_PROMPT_CACHE: dict[Path, str] = {}
