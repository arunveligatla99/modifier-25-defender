"""Hybrid retrieval package (EPIC-002).

Composes:

- :mod:`app.retrieval.chunker` document chunking (200 to 400 tokens, 50-token overlap)
- :mod:`app.retrieval.metadata` per-chunk metadata enrichment
- :mod:`app.retrieval.bm25` sparse retrieval
- :mod:`app.retrieval.qdrant` dense retrieval wrapper
- :mod:`app.retrieval.fusion` Reciprocal Rank Fusion (k=60)
- :mod:`app.retrieval.reranker` cross-encoder reranker
- :mod:`app.retrieval.retriever` orchestrating ``Retriever`` class

All retrieved chunks carry source metadata for citation rendering and for
authority-based conflict resolution (Constitution: CMS > AAPC > JARALL >
OTHER).
"""

from app.retrieval.bm25 import BM25Index
from app.retrieval.chunker import Chunk, ChunkerConfig, chunk_document
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.metadata import build_chunk_id, enrich_chunk
from app.retrieval.reranker import CrossEncoderReranker, RerankerStub
from app.retrieval.retriever import RetrievalResult, Retriever

__all__ = [
    "BM25Index",
    "Chunk",
    "ChunkerConfig",
    "CrossEncoderReranker",
    "RerankerStub",
    "RetrievalResult",
    "Retriever",
    "build_chunk_id",
    "chunk_document",
    "enrich_chunk",
    "reciprocal_rank_fusion",
]
