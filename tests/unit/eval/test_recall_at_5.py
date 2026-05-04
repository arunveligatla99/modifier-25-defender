"""Unit tests for eval.retrieval.recall_at_5."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.corpus import CorpusChunk
from eval.retrieval.recall_at_5 import (
    RetrievalQuestion,
    evaluate_recall_at_5,
)


def _chunk(chunk_id: str, source: str, text: str = "x") -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        text=text,
        source_document=source,
        authority_tier="OTHER",
    )


@dataclass
class _Result:
    query: str
    chunks: list[tuple[CorpusChunk, float]]


class FakeRetriever:
    """Fake retriever returning a fixed mapping from question to top-k chunks."""

    def __init__(self, mapping: dict[str, list[tuple[CorpusChunk, float]]]) -> None:
        self.mapping = mapping

    def search(self, query: str) -> _Result:
        return _Result(query=query, chunks=self.mapping.get(query, []))


def test_recall_when_expected_source_in_top_5() -> None:
    qs = [
        RetrievalQuestion(
            question_id="q01",
            question="what does cms say",
            expected_source_documents=["cms.txt"],
        )
    ]
    retriever = FakeRetriever(mapping={"what does cms say": [(_chunk("a", "cms.txt"), 0.9)]})
    report = evaluate_recall_at_5(retriever, qs)
    assert report.total == 1
    assert report.hits == 1
    assert report.recall_at_5 == 1.0
    assert report.per_question == {"q01": True}


def test_recall_when_expected_source_missing() -> None:
    qs = [
        RetrievalQuestion(
            question_id="q01",
            question="x",
            expected_source_documents=["cms.txt"],
        )
    ]
    retriever = FakeRetriever(mapping={"x": [(_chunk("a", "other.txt"), 0.9)]})
    report = evaluate_recall_at_5(retriever, qs)
    assert report.recall_at_5 == 0.0
    assert report.per_question == {"q01": False}


def test_recall_truncates_to_top_5() -> None:
    qs = [
        RetrievalQuestion(
            question_id="q01",
            question="x",
            expected_source_documents=["cms.txt"],
        )
    ]
    # Relevant chunk in position 6 should not count.
    chunks = [(_chunk(f"c{i}", "irrelevant.txt"), 1.0 - i * 0.01) for i in range(5)]
    chunks.append((_chunk("c5", "cms.txt"), 0.5))
    retriever = FakeRetriever(mapping={"x": chunks})
    report = evaluate_recall_at_5(retriever, qs)
    assert report.recall_at_5 == 0.0


def test_recall_keyword_fallback() -> None:
    qs = [
        RetrievalQuestion(
            question_id="q01",
            question="x",
            expected_chunk_keywords=["modifier 25", "distinct"],
        )
    ]
    matching = _chunk("a", "x.txt", text="The Modifier 25 distinct CC matters.")
    retriever = FakeRetriever(mapping={"x": [(matching, 0.9)]})
    report = evaluate_recall_at_5(retriever, qs)
    assert report.hits == 1


def test_no_questions_yields_zero() -> None:
    report = evaluate_recall_at_5(FakeRetriever(mapping={}), [])
    assert report.total == 0
    assert report.recall_at_5 == 0.0


def test_aggregate_ratio() -> None:
    qs = [
        RetrievalQuestion(
            question_id="q01",
            question="hit",
            expected_source_documents=["cms.txt"],
        ),
        RetrievalQuestion(
            question_id="q02",
            question="miss",
            expected_source_documents=["cms.txt"],
        ),
    ]
    retriever = FakeRetriever(
        mapping={
            "hit": [(_chunk("a", "cms.txt"), 0.9)],
            "miss": [(_chunk("b", "other.txt"), 0.9)],
        }
    )
    report = evaluate_recall_at_5(retriever, qs)
    assert report.total == 2
    assert report.hits == 1
    assert report.recall_at_5 == 0.5
