"""Qdrant dense retrieval wrapper.

The wrapper exposes a narrow interface (``index``, ``search``) that takes a
list of :class:`CorpusChunk` and a query embedding. Embedding the chunks and
the query is the caller's responsibility; this module does not invoke the
OpenAI embedding API directly so it can be unit-tested with stub vectors.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, cast

from app.schemas.corpus import CorpusChunk

logger = logging.getLogger(__name__)


class _QdrantClientLike(Protocol):
    """Protocol over the small subset of qdrant-client that we use."""

    def recreate_collection(self, **kwargs: Any) -> Any: ...
    def upsert(self, **kwargs: Any) -> Any: ...
    def search(self, **kwargs: Any) -> Any: ...


class QdrantIndex:
    """Thin Qdrant wrapper over a single collection.

    Attributes:
        url: Qdrant URL.
        collection: Collection name. Defaults to ``m25d-corpus``.
        vector_size: Embedding dimensionality. Defaults to 3072 for
            ``text-embedding-3-large``.
    """

    def __init__(
        self,
        *,
        url: str = "http://localhost:6333",
        collection: str = "m25d-corpus",
        vector_size: int = 3072,
        client: _QdrantClientLike | None = None,
    ) -> None:
        self.url = url
        self.collection = collection
        self.vector_size = vector_size
        self._client: _QdrantClientLike | None = client

    def _connect(self) -> _QdrantClientLike:
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "qdrant-client not available; install dev extras (uv sync --extra dev)"
            ) from exc
        client = cast(_QdrantClientLike, QdrantClient(url=self.url))
        self._client = client
        return client

    def reset(self) -> None:
        """Drop and recreate the collection. Idempotent. AC-002-6."""
        client = self._connect()
        from qdrant_client.http import models as qmodels

        client.recreate_collection(
            collection_name=self.collection,
            vectors_config=qmodels.VectorParams(
                size=self.vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def index(
        self,
        chunks: list[CorpusChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert chunk embeddings into the collection.

        The chunk's ``chunk_id`` is used as the Qdrant point ID, so re-indexing
        the same chunks with the same embeddings is idempotent.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"index: chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must match"
            )
        client = self._connect()
        from qdrant_client.http import models as qmodels

        points = [
            qmodels.PointStruct(
                id=_hash_id(chunk.chunk_id),
                vector=embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "source_document": chunk.source_document,
                    "section_heading": chunk.section_heading,
                    "publication_date": (
                        chunk.publication_date.isoformat() if chunk.publication_date else None
                    ),
                    "authority_tier": chunk.authority_tier,
                    "text": chunk.text,
                },
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        client.upsert(collection_name=self.collection, points=points)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 20,
    ) -> list[tuple[CorpusChunk, float]]:
        """Return the top-k nearest chunks to ``query_embedding``."""
        client = self._connect()
        results = client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
        )
        out: list[tuple[CorpusChunk, float]] = []
        for hit in results:
            payload = getattr(hit, "payload", None) or {}
            out.append(
                (
                    _payload_to_chunk(payload),
                    float(getattr(hit, "score", 0.0)),
                )
            )
        return out


def _hash_id(chunk_id: str) -> int:
    """Map a string chunk_id to a deterministic 64-bit Qdrant point id."""
    import hashlib

    digest = hashlib.sha1(chunk_id.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _payload_to_chunk(payload: dict[str, Any]) -> CorpusChunk:
    from datetime import date as _date

    pub = payload.get("publication_date")
    pub_dt: _date | None = _date.fromisoformat(pub) if isinstance(pub, str) else None
    return CorpusChunk(
        chunk_id=payload["chunk_id"],
        text=payload["text"],
        source_document=payload["source_document"],
        section_heading=payload.get("section_heading"),
        publication_date=pub_dt,
        authority_tier=payload["authority_tier"],
    )
