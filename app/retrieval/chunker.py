"""Token-aware document chunker.

Chunks are 200 to 400 tokens with 50-token overlap (per spec EPIC-002 5.1).
Token counts use the OpenAI ``cl100k_base`` encoder via ``tiktoken`` so that
chunk sizes match the embedding model's view of the text. Falls back to a
whitespace word counter when ``tiktoken`` is unavailable, which keeps unit
tests fast on machines that have not pre-fetched the encoding files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _Tokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...
    def decode(self, ids: list[int]) -> str: ...


class _WhitespaceTokenizer:
    """Fallback tokenizer used when tiktoken is not available."""

    def encode(self, text: str) -> list[int]:
        # Use the index of each whitespace-split word as the "token id".
        return list(range(len(text.split())))

    def decode(self, ids: list[int]) -> str:  # pragma: no cover - unused
        return " ".join(str(i) for i in ids)


def _load_tokenizer() -> tuple[_Tokenizer, bool]:
    """Return a tokenizer plus ``True`` when the real tiktoken encoder loaded."""
    try:
        import tiktoken
    except ImportError:  # pragma: no cover - tiktoken is in deps
        return _WhitespaceTokenizer(), False
    try:
        return tiktoken.get_encoding("cl100k_base"), True
    except Exception:  # pragma: no cover - offline machines
        return _WhitespaceTokenizer(), False


@dataclass(frozen=True)
class ChunkerConfig:
    """Chunker tuning knobs.

    Attributes:
        target_tokens: Target chunk length in tokens. Spec range 200 to 400.
        overlap_tokens: Number of tokens overlapping between consecutive
            chunks. Spec value 50.
        max_tokens: Hard cap on a single chunk to protect downstream agents.
    """

    target_tokens: int = 300
    overlap_tokens: int = 50
    max_tokens: int = 400


@dataclass(frozen=True)
class Chunk:
    """A token-aware chunk of a source document.

    Attributes:
        text: Decoded chunk text.
        token_count: Token count of the chunk under the active tokenizer.
        start_token: Inclusive start index in the source document's token list.
        end_token: Exclusive end index in the source document's token list.
    """

    text: str
    token_count: int
    start_token: int
    end_token: int


def chunk_document(text: str, config: ChunkerConfig | None = None) -> list[Chunk]:
    """Split a document into overlapping token-aware chunks.

    Args:
        text: The source document text.
        config: Optional chunker configuration.

    Returns:
        A list of :class:`Chunk` objects covering the document. Chunks have
        approximately ``config.target_tokens`` tokens with
        ``config.overlap_tokens`` tokens of overlap between neighbors. The
        last chunk is shorter when the document does not divide evenly.

    Raises:
        ValueError: If the configuration is internally inconsistent (e.g.
            overlap >= target).
    """
    cfg = config or ChunkerConfig()
    if cfg.overlap_tokens >= cfg.target_tokens:
        raise ValueError("ChunkerConfig: overlap_tokens must be strictly less than target_tokens")
    if cfg.target_tokens > cfg.max_tokens:
        raise ValueError("ChunkerConfig: target_tokens must be <= max_tokens")

    if not text.strip():
        return []

    tokenizer, real = _load_tokenizer()
    if real:
        tokens = tokenizer.encode(text)
        return _chunk_real_tokens(tokens, tokenizer, cfg)
    return _chunk_whitespace(text, cfg)


def _chunk_real_tokens(tokens: list[int], tokenizer: _Tokenizer, cfg: ChunkerConfig) -> list[Chunk]:
    """Chunk using a real token list; preserves token offsets and decoding."""
    chunks: list[Chunk] = []
    if not tokens:
        return chunks
    step = cfg.target_tokens - cfg.overlap_tokens
    start = 0
    while start < len(tokens):
        end = min(start + cfg.target_tokens, len(tokens))
        slice_ = tokens[start:end]
        chunks.append(
            Chunk(
                text=tokenizer.decode(slice_),
                token_count=len(slice_),
                start_token=start,
                end_token=end,
            )
        )
        if end == len(tokens):
            break
        start += step
    return chunks


def _chunk_whitespace(text: str, cfg: ChunkerConfig) -> list[Chunk]:
    """Fallback chunker for environments without tiktoken."""
    words = text.split()
    if not words:
        return []
    chunks: list[Chunk] = []
    step = cfg.target_tokens - cfg.overlap_tokens
    start = 0
    while start < len(words):
        end = min(start + cfg.target_tokens, len(words))
        slice_ = words[start:end]
        chunks.append(
            Chunk(
                text=" ".join(slice_),
                token_count=len(slice_),
                start_token=start,
                end_token=end,
            )
        )
        if end == len(words):
            break
        start += step
    return chunks
