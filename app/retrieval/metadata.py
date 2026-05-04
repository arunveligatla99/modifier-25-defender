"""Per-chunk metadata enrichment.

Builds :class:`CorpusChunk` instances from raw text plus document metadata.
The chunk identifier is derived deterministically from the source document
identifier and the chunk's token offsets so that a re-index produces the
same identifiers (AC-002-6 idempotency).
"""

from __future__ import annotations

import hashlib
from datetime import date

from app.retrieval.chunker import Chunk
from app.schemas.corpus import AuthorityTier, CorpusChunk


def build_chunk_id(source_document: str, start_token: int, end_token: int) -> str:
    """Return a stable chunk identifier from source + offsets.

    The hash is short (12 hex chars) so identifiers stay readable in error
    messages and citation panels. Collisions within a corpus this small
    are vanishingly unlikely; if a future v1.1 corpus expansion makes that
    a concern, widen the hash slice.
    """
    digest = hashlib.sha1(f"{source_document}|{start_token}|{end_token}".encode()).hexdigest()[:12]
    safe_doc = source_document.lower().replace(" ", "-")
    return f"{safe_doc}|{digest}"


def enrich_chunk(
    chunk: Chunk,
    *,
    source_document: str,
    authority_tier: AuthorityTier,
    section_heading: str | None = None,
    publication_date: date | None = None,
) -> CorpusChunk:
    """Wrap a raw :class:`Chunk` in a :class:`CorpusChunk` with metadata."""
    return CorpusChunk(
        chunk_id=build_chunk_id(source_document, chunk.start_token, chunk.end_token),
        text=chunk.text,
        source_document=source_document,
        section_heading=section_heading,
        publication_date=publication_date,
        authority_tier=authority_tier,
    )
