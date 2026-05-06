"""Reference corpus schema.

Produced by EPIC-002. Each chunk carries metadata used for citation rendering
and for authority-based conflict resolution (CMS > AAPC > JARALL > OTHER).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuthorityTier = Literal["CMS", "AAPC", "JARALL", "OTHER"]
"""Authority ranking used when retrieved chunks contradict."""


class CorpusChunk(BaseModel):
    """A retrievable unit of the reference corpus.

    Attributes:
        chunk_id: Stable across re-indexes given the same source documents
            (AC-002-6 idempotency).
        text: The chunk text, 200 to 400 tokens approximately.
        source_document: File name or URL of the source document.
        section_heading: Optional section heading for traceable rendering.
        publication_date: Optional publication date.
        authority_tier: CMS > AAPC > JARALL > OTHER for conflict resolution.

    Notes:
        Embeddings are not stored on the model itself; they live in Qdrant's
        payload alongside the chunk_id. This separation keeps the source-of-
        truth JSON portable and lets the embedding model change without
        invalidating the chunk identifier.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    source_document: str = Field(..., min_length=1)
    section_heading: str | None = None
    publication_date: date | None = None
    authority_tier: AuthorityTier
