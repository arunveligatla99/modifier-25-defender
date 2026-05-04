"""LLM client package.

Wraps the OpenAI SDK with a content-hash cache (R7 / Q5). Cache key:
SHA-256 of prompt + retrieval-context JSON + model version + temperature +
provider tag. Including model version and temperature forces full
re-evaluation on a model bump, preventing silent eval drift.
"""

from app.llm.embeddings import embed_batch, embed_text
from app.llm.openai_client import (
    CachedLLMClient,
    LLMResponse,
    cache_key,
)

__all__ = [
    "CachedLLMClient",
    "LLMResponse",
    "cache_key",
    "embed_batch",
    "embed_text",
]
