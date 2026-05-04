"""OpenAI client wrapper with on-disk content-hash cache.

Implements R7 / Q5: cache key includes prompt text, retrieval context,
model version, temperature, and provider tag. A model upgrade or temperature
change therefore forces full re-evaluation rather than masking drift behind a
stale cache hit. Stable on a single host; the cache is gitignored.

The wrapper is intentionally narrow:

- Only the chat completion code path is exposed (synthesis agents use it).
- Response is captured as a structured ``LLMResponse`` model so downstream
  agents see Pydantic types, not provider-specific dicts.
- The OpenAI SDK is imported lazily so unit tests can run without the
  package installed in environments where it is not yet pinned.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

PROVIDER_TAG = "openai"


class LLMResponse(BaseModel):
    """Structured response from a chat completion call.

    Attributes:
        content: Raw assistant message content.
        model: Model name reported by the provider.
        prompt_tokens: Prompt token count from usage.
        completion_tokens: Completion token count from usage.
        cached: True when the response was served from the local cache.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached: bool = False


class _OpenAIClientLike(Protocol):
    """Protocol matching the subset of the OpenAI SDK we use."""

    def chat_completions_create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, Any] | None,
    ) -> Any: ...


@dataclass(frozen=True)
class CacheKeyInputs:
    """Inputs that determine cache identity.

    Attributes:
        prompt: The full prompt text or serialized message list.
        retrieval_context: JSON-serialized retrieval context payload (may be
            an empty object when the call has no retrieval).
        model: Provider-reported model identifier.
        temperature: Sampling temperature.
        provider: Provider tag (``"openai"`` for v1).
    """

    prompt: str
    retrieval_context: str
    model: str
    temperature: float
    provider: str


def cache_key(inputs: CacheKeyInputs) -> str:
    """Compute a deterministic SHA-256 cache key from the inputs.

    Args:
        inputs: The cache-determining fields. See :class:`CacheKeyInputs`.

    Returns:
        Hex-encoded SHA-256 digest, 64 characters.
    """
    payload = json.dumps(
        {
            "prompt": inputs.prompt,
            "retrieval_context": inputs.retrieval_context,
            "model": inputs.model,
            "temperature": inputs.temperature,
            "provider": inputs.provider,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachedLLMClient(BaseModel):
    """OpenAI chat completion wrapper with on-disk caching.

    Attributes:
        cache_dir: Directory used for the on-disk cache.
        model: Default model for chat completions.
        temperature: Default sampling temperature.
        api_key: OpenAI API key.

    Notes:
        Cache writes are atomic per file. Reads do not validate timestamps;
        the cache is invalidated by changing any cache key input (model,
        temperature, prompt, retrieval context, provider).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cache_dir: Path = Field(default=Path("eval/.cache"))
    model: str = "gpt-4o"
    temperature: float = 0.0
    api_key: str = Field(default="", repr=False)

    def model_post_init(self, _ctx: Any) -> None:
        """Ensure the cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> LLMResponse | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cache read failed for %s: %s", key, exc)
            return None
        return LLMResponse(**{**data, "cached": True})

    def _write_cache(self, key: str, response: LLMResponse) -> None:
        path = self._cache_path(key)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            response.model_dump_json(exclude={"cached"}),
            encoding="utf-8",
        )
        tmp.replace(path)

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        retrieval_context: dict[str, Any] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
        client: _OpenAIClientLike | None = None,
    ) -> LLMResponse:
        """Run a chat completion, hitting the cache when possible.

        Args:
            messages: OpenAI-style message list.
            retrieval_context: Optional retrieval payload included in the
                cache key. Pass the same object you fed into the prompt.
            model: Override the default model.
            temperature: Override the default temperature.
            response_format: Optional structured-output spec.
            client: Injected client for testing. Production callers leave
                this ``None``; the wrapper instantiates the OpenAI SDK
                lazily.

        Returns:
            The structured response, with ``cached`` set to True on a hit.

        Raises:
            RuntimeError: When no API key is configured and the cache misses.
        """
        used_model = model or self.model
        used_temp = self.temperature if temperature is None else temperature
        prompt_blob = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        ctx_blob = json.dumps(retrieval_context or {}, sort_keys=True, ensure_ascii=False)

        key = cache_key(
            CacheKeyInputs(
                prompt=prompt_blob,
                retrieval_context=ctx_blob,
                model=used_model,
                temperature=used_temp,
                provider=PROVIDER_TAG,
            )
        )

        hit = self._read_cache(key)
        if hit is not None:
            logger.debug("LLM cache hit %s", key)
            return hit

        if client is None:
            if not self.api_key:
                raise RuntimeError(
                    "CachedLLMClient: cache miss and no API key configured. "
                    "Set OPENAI_API_KEY or pass an injected client for tests."
                )
            client = _make_default_client(self.api_key)

        raw = client.chat_completions_create(
            model=used_model,
            messages=messages,
            temperature=used_temp,
            response_format=response_format,
        )
        response = _coerce_response(raw, used_model)
        self._write_cache(key, response)
        return response


def _make_default_client(api_key: str) -> _OpenAIClientLike:
    """Lazy adapter around the OpenAI SDK matching :class:`_OpenAIClientLike`."""
    from openai import OpenAI  # imported lazily so tests do not require the SDK

    sdk_client = OpenAI(api_key=api_key)

    class _Adapter:
        def chat_completions_create(
            self,
            *,
            model: str,
            messages: list[dict[str, str]],
            temperature: float,
            response_format: dict[str, Any] | None,
        ) -> Any:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            return sdk_client.chat.completions.create(**kwargs)

    return _Adapter()


def _coerce_response(raw: Any, fallback_model: str) -> LLMResponse:
    """Coerce a provider response into a structured :class:`LLMResponse`."""
    try:
        choice = raw.choices[0]
        content = choice.message.content or ""
        usage = getattr(raw, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        model = getattr(raw, "model", fallback_model)
    except (AttributeError, IndexError) as exc:
        raise RuntimeError(f"Unexpected LLM response shape: {exc}") from exc

    return LLMResponse(
        content=content,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached=False,
    )
