"""Unit tests for app.retrieval.fusion."""

from __future__ import annotations

from app.retrieval.fusion import DEFAULT_K, reciprocal_rank_fusion
from app.schemas.corpus import CorpusChunk


def _chunk(chunk_id: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        text="x",
        source_document="x",
        authority_tier="OTHER",
    )


class TestReciprocalRankFusion:
    def test_single_list_passes_through(self) -> None:
        a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
        ranked = [(a, 10.0), (b, 5.0), (c, 1.0)]
        fused = reciprocal_rank_fusion(ranked)
        assert [chunk.chunk_id for chunk, _ in fused] == ["a", "b", "c"]

    def test_two_lists_sum_contributions(self) -> None:
        a, b = _chunk("a"), _chunk("b")
        # 'a' is rank 0 in list 1 and rank 1 in list 2.
        # 'b' is rank 1 in list 1 and rank 0 in list 2.
        l1 = [(a, 10.0), (b, 5.0)]
        l2 = [(b, 10.0), (a, 5.0)]
        fused = reciprocal_rank_fusion(l1, l2)
        # Equal contributions: both should sum to 1/61 + 1/62 each.
        assert {chunk.chunk_id for chunk, _ in fused} == {"a", "b"}
        scores = {chunk.chunk_id: score for chunk, score in fused}
        assert abs(scores["a"] - scores["b"]) < 1e-9
        expected = 1.0 / (DEFAULT_K + 1) + 1.0 / (DEFAULT_K + 2)
        assert abs(scores["a"] - expected) < 1e-9

    def test_top_n_truncates(self) -> None:
        chunks = [_chunk(f"c{i}") for i in range(10)]
        ranked = [(c, 1.0) for c in chunks]
        fused = reciprocal_rank_fusion(ranked, top_n=3)
        assert len(fused) == 3

    def test_chunk_only_in_one_list(self) -> None:
        a = _chunk("a")
        b = _chunk("b")
        l1 = [(a, 10.0)]
        l2 = [(b, 10.0)]
        fused = reciprocal_rank_fusion(l1, l2)
        assert {chunk.chunk_id for chunk, _ in fused} == {"a", "b"}

    def test_empty_lists(self) -> None:
        assert reciprocal_rank_fusion() == []
        assert reciprocal_rank_fusion([], []) == []
