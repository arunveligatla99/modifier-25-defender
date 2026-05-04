"""Recall@5 retrieval eval harness (T119).

For each question in ``data/retrieval_eval/questions.jsonl``, run the
retriever and check whether at least one of the expected source documents
appears in the top-5 reranked results. Recall@5 is the fraction of
questions for which this is true.

The harness is intentionally tolerant about chunk identity: relevance is
matched on ``source_document``, since chunk_ids change as the corpus is
re-chunked. Real corpus ingestion (T109) may also pin specific chunk_ids
in the eval set; the harness supports both modes.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

DEFAULT_QUESTIONS_PATH = Path("data/retrieval_eval/questions.jsonl")


class _RetrieverLike(Protocol):
    def search(self, query: str) -> object: ...


@dataclass(frozen=True)
class RetrievalQuestion:
    """One entry in the retrieval eval set."""

    question_id: str
    question: str
    expected_source_documents: list[str] = field(default_factory=list)
    expected_chunk_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecallReport:
    """Output of the recall@5 harness.

    Attributes:
        total: Number of questions evaluated.
        hits: Number of questions where a relevant chunk appeared in the
            top-5 reranked output.
        recall_at_5: ``hits / total``, or 0.0 when total == 0.
        per_question: Per-question pass/fail flags keyed by question_id.
    """

    total: int
    hits: int
    recall_at_5: float
    per_question: dict[str, bool]


def load_questions(path: Path = DEFAULT_QUESTIONS_PATH) -> list[RetrievalQuestion]:
    """Load the retrieval eval questions from a JSONL file."""
    if not path.exists():
        return []
    out: list[RetrievalQuestion] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        out.append(
            RetrievalQuestion(
                question_id=record["question_id"],
                question=record["question"],
                expected_source_documents=record.get("expected_source_documents", []),
                expected_chunk_keywords=record.get("expected_chunk_keywords", []),
            )
        )
    return out


def evaluate_recall_at_5(
    retriever: _RetrieverLike,
    questions: Iterable[RetrievalQuestion] | None = None,
    *,
    questions_path: Path = DEFAULT_QUESTIONS_PATH,
) -> RecallReport:
    """Compute recall@5 for ``retriever`` against ``questions``.

    Args:
        retriever: Object exposing ``search(query) -> RetrievalResult`` where
            ``RetrievalResult.chunks`` is a list of ``(CorpusChunk, score)``
            pairs.
        questions: Optional iterable of :class:`RetrievalQuestion`. When
            ``None``, loads from ``questions_path``.
        questions_path: Path to the questions JSONL file.

    Returns:
        A :class:`RecallReport` with per-question flags and the aggregate.
    """
    qs = list(questions) if questions is not None else load_questions(questions_path)
    if not qs:
        return RecallReport(total=0, hits=0, recall_at_5=0.0, per_question={})

    per_question: dict[str, bool] = {}
    hits = 0
    for q in qs:
        result = retriever.search(q.question)
        top_chunks = list(getattr(result, "chunks", []))[:5]
        relevant = _is_relevant(top_chunks, q)
        per_question[q.question_id] = relevant
        if relevant:
            hits += 1
    total = len(qs)
    return RecallReport(
        total=total,
        hits=hits,
        recall_at_5=hits / total if total else 0.0,
        per_question=per_question,
    )


def _is_relevant(top_chunks: list[object], q: RetrievalQuestion) -> bool:
    """Return True when at least one expected source appears in ``top_chunks``."""
    if not q.expected_source_documents and not q.expected_chunk_keywords:
        return False
    for chunk_score in top_chunks:
        chunk = chunk_score[0] if isinstance(chunk_score, tuple) else chunk_score
        source = getattr(chunk, "source_document", "")
        text = getattr(chunk, "text", "")
        if any(src == source for src in q.expected_source_documents):
            return True
        if q.expected_chunk_keywords and all(
            kw.lower() in text.lower() for kw in q.expected_chunk_keywords
        ):
            return True
    return False
