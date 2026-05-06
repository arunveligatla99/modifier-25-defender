"""Reciprocal Rank Fusion (RRF) with k=60.

RRF combines multiple ranked lists into one without needing comparable
score scales. The classic RRF formula assigns each item a score of
``1 / (k + rank)`` summed across the source lists; we follow that.
"""

from __future__ import annotations

from app.schemas.corpus import CorpusChunk

DEFAULT_K = 60


def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[CorpusChunk, float]],
    k: int = DEFAULT_K,
    top_n: int | None = None,
) -> list[tuple[CorpusChunk, float]]:
    """Fuse multiple ranked lists with Reciprocal Rank Fusion.

    Args:
        ranked_lists: One or more lists of ``(chunk, score)`` pairs. Score
            magnitudes are ignored; only rank position matters.
        k: RRF damping constant. Default 60 per spec EPIC-002 5.2.
        top_n: Truncate the fused result to this length (default: keep all).

    Returns:
        A list of ``(chunk, fused_score)`` pairs sorted descending by fused
        score. Chunk identity is determined by ``chunk.chunk_id``.
    """
    fused: dict[str, tuple[CorpusChunk, float]] = {}
    for ranked in ranked_lists:
        for rank, (chunk, _score) in enumerate(ranked):
            contribution = 1.0 / (k + rank + 1)  # +1 because rank is 0-indexed
            if chunk.chunk_id in fused:
                _, prior = fused[chunk.chunk_id]
                fused[chunk.chunk_id] = (chunk, prior + contribution)
            else:
                fused[chunk.chunk_id] = (chunk, contribution)
    out = sorted(fused.values(), key=lambda pair: pair[1], reverse=True)
    if top_n is not None:
        return out[:top_n]
    return out
