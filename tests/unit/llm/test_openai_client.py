"""Unit tests for app.llm.openai_client."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app.llm.openai_client import (
    CachedLLMClient,
    CacheKeyInputs,
    LLMResponse,
    cache_key,
)


class FakeProviderResponse:
    """Minimal stand-in for the OpenAI SDK response shape."""

    class _Usage:
        def __init__(self, p: int = 10, c: int = 20) -> None:
            self.prompt_tokens = p
            self.completion_tokens = c

    class _Message:
        def __init__(self, content: str) -> None:
            self.content = content

    class _Choice:
        def __init__(self, content: str) -> None:
            self.message = FakeProviderResponse._Message(content)

    def __init__(self, content: str = "ok", model: str = "gpt-4o") -> None:
        self.choices = [FakeProviderResponse._Choice(content)]
        self.usage = FakeProviderResponse._Usage()
        self.model = model


class FakeClient:
    def __init__(self, content: str = "ok") -> None:
        self.calls = 0
        self._content = content

    def chat_completions_create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, Any] | None,
    ) -> Any:
        self.calls += 1
        return FakeProviderResponse(content=self._content, model=model)


@pytest.fixture
def client(tmp_path: Path) -> CachedLLMClient:
    return CachedLLMClient(cache_dir=tmp_path / "cache", model="gpt-4o", temperature=0.0)


class TestCacheKey:
    def test_deterministic(self) -> None:
        k1 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o", 0.0, "openai"))
        k2 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o", 0.0, "openai"))
        assert k1 == k2

    def test_model_change_invalidates(self) -> None:
        k1 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o", 0.0, "openai"))
        k2 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o-mini", 0.0, "openai"))
        assert k1 != k2

    def test_temperature_change_invalidates(self) -> None:
        k1 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o", 0.0, "openai"))
        k2 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o", 0.5, "openai"))
        assert k1 != k2

    def test_provider_change_invalidates(self) -> None:
        k1 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o", 0.0, "openai"))
        k2 = cache_key(CacheKeyInputs("p", "{}", "gpt-4o", 0.0, "anthropic"))
        assert k1 != k2

    def test_retrieval_context_change_invalidates(self) -> None:
        k1 = cache_key(CacheKeyInputs("p", '{"a":1}', "gpt-4o", 0.0, "openai"))
        k2 = cache_key(CacheKeyInputs("p", '{"a":2}', "gpt-4o", 0.0, "openai"))
        assert k1 != k2


class TestCachedLLMClient:
    def test_first_call_misses_then_caches(self, client: CachedLLMClient) -> None:
        fake = FakeClient(content="hello")
        msgs = [{"role": "user", "content": "hi"}]

        first = client.chat(messages=msgs, client=fake)
        assert isinstance(first, LLMResponse)
        assert first.cached is False
        assert fake.calls == 1

        second = client.chat(messages=msgs, client=fake)
        assert second.cached is True
        assert fake.calls == 1

    def test_temperature_change_misses_cache(self, client: CachedLLMClient) -> None:
        fake = FakeClient(content="hi")
        msgs = [{"role": "user", "content": "hi"}]
        client.chat(messages=msgs, client=fake, temperature=0.0)
        client.chat(messages=msgs, client=fake, temperature=0.5)
        assert fake.calls == 2

    def test_retrieval_context_change_misses_cache(self, client: CachedLLMClient) -> None:
        fake = FakeClient(content="hi")
        msgs = [{"role": "user", "content": "hi"}]
        client.chat(messages=msgs, client=fake, retrieval_context={"chunks": ["a"]})
        client.chat(messages=msgs, client=fake, retrieval_context={"chunks": ["b"]})
        assert fake.calls == 2

    def test_missing_api_key_raises_on_miss(self, client: CachedLLMClient) -> None:
        # Default api_key is empty string. With no injected client and a cache
        # miss, the wrapper should raise rather than swallow the misconfig.
        with pytest.raises(RuntimeError, match="no API key configured"):
            client.chat(messages=[{"role": "user", "content": "x"}])
