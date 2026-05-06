"""OpenAI embedding helper.

Thin wrapper for ``text-embedding-3-large``. Used by:

- ``app.retrieval.cli`` (``make corpus``) when pushing chunk embeddings into
  Qdrant.
- ``app.api.routes`` for query-time dense retrieval.

Includes an in-memory LRU and a disk-backed content-hash cache so the
eval harness does not re-bill OpenAI for fixed inputs and so CI runs
deterministically against committed cache files. The disk cache lives
at ``<llm_cache_dir>/embeddings/`` and is keyed by SHA-256 of
``(model, text)``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.infra.settings import get_settings

logger = logging.getLogger(__name__)


class _OpenAIEmbedderLike(Protocol):
    """Subset of the OpenAI SDK we call."""

    def embeddings_create(self, *, model: str, input: str | list[str]) -> Any: ...


def embed_text(
    text: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    client: _OpenAIEmbedderLike | None = None,
) -> list[float]:
    """Return the embedding vector for ``text``.

    Args:
        text: Input string. Empty strings are mapped to a zero vector to
            avoid spurious API calls.
        model: Override the configured embedding model.
        api_key: Override the configured API key.
        client: Inject for testing.

    Returns:
        The dense embedding as a Python list of floats.
    """
    settings = get_settings()
    used_model = model or settings.embedding_model
    used_key = api_key if api_key is not None else settings.openai_api_key
    if not text.strip():
        return [0.0] * 8  # placeholder; never reaches the API
    cached = _cached_embed(text, used_model)
    if cached is not None:
        return list(cached)
    disk_cached = _disk_cache_read(text, used_model, settings.llm_cache_dir)
    if disk_cached is not None:
        _cache_set(text, used_model, tuple(disk_cached))
        return disk_cached
    if client is None:
        client = _make_default_client(used_key)
    raw = client.embeddings_create(model=used_model, input=text)
    vector = _vector_from(raw)
    _cache_set(text, used_model, tuple(vector))
    _disk_cache_write(text, used_model, vector, settings.llm_cache_dir)
    return vector


def embed_batch(
    texts: list[str],
    *,
    model: str | None = None,
    api_key: str | None = None,
    client: _OpenAIEmbedderLike | None = None,
) -> list[list[float]]:
    """Embed multiple texts in one API call when possible."""
    settings = get_settings()
    used_model = model or settings.embedding_model
    used_key = api_key if api_key is not None else settings.openai_api_key
    if not texts:
        return []
    if client is None:
        client = _make_default_client(used_key)
    raw = client.embeddings_create(model=used_model, input=texts)
    vectors = _vectors_from(raw)
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"embed_batch: provider returned {len(vectors)} vectors for {len(texts)} inputs"
        )
    return vectors


def _make_default_client(api_key: str) -> _OpenAIEmbedderLike:
    """Lazy adapter around the OpenAI SDK."""
    from openai import OpenAI

    sdk = OpenAI(api_key=api_key)

    class _Adapter:
        def embeddings_create(self, *, model: str, input: str | list[str]) -> Any:
            return sdk.embeddings.create(model=model, input=input)

    return _Adapter()


def _vector_from(raw: Any) -> list[float]:
    """Extract a single embedding vector from a provider response."""
    try:
        return list(raw.data[0].embedding)
    except (AttributeError, IndexError) as exc:
        raise RuntimeError(f"unexpected embedding response shape: {exc}") from exc


def _vectors_from(raw: Any) -> list[list[float]]:
    """Extract a batch of embedding vectors."""
    try:
        return [list(item.embedding) for item in raw.data]
    except (AttributeError, IndexError) as exc:
        raise RuntimeError(f"unexpected embedding batch response shape: {exc}") from exc


# ---------------------------------------------------------------------------
# In-memory cache (process lifetime). The on-disk content-hash cache used by
# the chat client is not appropriate here because embeddings keys are short
# and the value is large; an LRU on (text, model) is the right shape.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1024)
def _cached_embed_lookup(text: str, model: str) -> tuple[float, ...] | None:
    """LRU cache helper. Returns None on miss; the writer populates it."""
    return None


_EMBED_CACHE: dict[tuple[str, str], tuple[float, ...]] = {}


def _cached_embed(text: str, model: str) -> tuple[float, ...] | None:
    return _EMBED_CACHE.get((text, model))


def _cache_set(text: str, model: str, vector: tuple[float, ...]) -> None:
    if len(_EMBED_CACHE) >= 4096:
        # Trim aggressively to avoid unbounded growth in long-lived processes.
        for key in list(_EMBED_CACHE.keys())[:1024]:
            _EMBED_CACHE.pop(key, None)
    _EMBED_CACHE[(text, model)] = vector


# ---------------------------------------------------------------------------
# Disk-backed content-hash cache. Same shape as the LLM cache: deterministic
# SHA-256 of (model, text) -> a JSON file containing the vector. Persisted
# across runs so CI does not re-bill embeddings for the eval question set.
# ---------------------------------------------------------------------------


def _disk_cache_dir(base_dir: Path) -> Path:
    return Path(base_dir) / "embeddings"


def _disk_cache_key(text: str, model: str) -> str:
    payload = json.dumps({"model": model, "text": text}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _disk_cache_read(text: str, model: str, base_dir: Path) -> list[float] | None:
    path = _disk_cache_dir(base_dir) / f"{_disk_cache_key(text, model)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        vec = data.get("vector")
        if isinstance(vec, list):
            return [float(v) for v in vec]
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("embedding cache read failed for %s: %s", path.name, exc)
    return None


def _disk_cache_write(text: str, model: str, vector: list[float], base_dir: Path) -> None:
    cache_dir = _disk_cache_dir(base_dir)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"{_disk_cache_key(text, model)}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"vector": vector}), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("embedding cache write failed: %s", exc)
