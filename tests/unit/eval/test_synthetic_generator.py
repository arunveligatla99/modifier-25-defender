"""Unit tests for the synthetic encounter generator (T106)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from eval.schemas import SyntheticEncounter
from eval.synthetic.cli import write_dataset
from eval.synthetic.generator import generate
from eval.synthetic.sampler import sample_with_constraints
from eval.synthetic.split import split_for


def _take(it: Iterator[SyntheticEncounter], n: int) -> list[SyntheticEncounter]:
    out: list[SyntheticEncounter] = []
    for _ in range(n):
        out.append(next(it))
    return out


class TestDeterminism:
    def test_same_seed_yields_same_stream(self) -> None:
        a = _take(iter(generate(seed=42, count=50)), 50)
        b = _take(iter(generate(seed=42, count=50)), 50)
        assert [e.encounter_id for e in a] == [e.encounter_id for e in b]
        assert [e.note_text for e in a] == [e.note_text for e in b]

    def test_different_seed_yields_different_stream(self) -> None:
        a = _take(iter(generate(seed=42, count=50)), 50)
        b = _take(iter(generate(seed=43, count=50)), 50)
        assert [e.encounter_id for e in a] != [e.encounter_id for e in b]


class TestStratification:
    def test_pass_fail_minimums(self) -> None:
        candidates = generate(seed=42, count=10_000)
        chosen = sample_with_constraints(candidates, target_count=100)
        assert len(chosen) == 100
        pass_count = sum(1 for e in chosen if e.ground_truth.overall == "PASS")
        fail_count = sum(1 for e in chosen if e.ground_truth.overall == "FAIL")
        assert pass_count >= 25  # AC-001-4
        assert fail_count >= 25  # AC-001-3

    def test_six_distinct_procedure_codes(self) -> None:
        candidates = generate(seed=42, count=10_000)
        chosen = sample_with_constraints(candidates, target_count=100)
        codes = {e.procedure_code for e in chosen}
        assert len(codes) >= 6  # AC-001-5

    def test_split_membership_balanced(self) -> None:
        candidates = generate(seed=42, count=10_000)
        chosen = sample_with_constraints(candidates, target_count=100)
        splits = [e.split for e in chosen]
        # Allow some slack on the 70/15/15 target since it is hash-based.
        assert 50 <= splits.count("train") <= 90
        assert 5 <= splits.count("dev") <= 25
        assert 5 <= splits.count("test") <= 25


class TestLabels:
    def test_overall_is_deterministic_aggregate(self) -> None:
        for e in _take(iter(generate(seed=42, count=50)), 50):
            sub = (
                e.ground_truth.distinct_cc,
                e.ground_truth.separate_exam,
                e.ground_truth.independent_mdm,
                e.ground_truth.site_specificity,
            )
            if "FAIL" in sub:
                assert e.ground_truth.overall == "FAIL"
            elif "WEAK" in sub:
                assert e.ground_truth.overall == "WEAK"
            else:
                assert e.ground_truth.overall == "PASS"

    def test_label_records_parameter_space_index(self) -> None:
        sample = next(iter(generate(seed=42, count=1)))
        idx = sample.ground_truth.parameter_space_index
        for key in (
            "presenting_condition",
            "diabetes",
            "neuropathy",
            "pvd",
            "procedure_type",
            "site",
            "em_level",
            "separable_problem",
            "site_specificity_stated",
            "mdm_separability",
            "exam_separability",
            "narrative_style",
        ):
            assert key in idx


class TestSplit:
    def test_split_is_stable(self) -> None:
        # Same encounter_id always lands in the same split.
        for eid in ("synth_0001_abc", "synth_0099_xyz", "synth_1234_deadbeef"):
            assert split_for(eid) == split_for(eid)

    def test_split_distribution_close_to_target(self) -> None:
        # Sample 1000 made-up IDs; expect ~70/15/15 within tolerance.
        from random import Random

        rng = Random(0)
        ids = [f"synth_{i:04d}_{rng.randrange(0, 0xFFFFFFFF):08x}" for i in range(1000)]
        counts = {"train": 0, "dev": 0, "test": 0}
        for eid in ids:
            counts[split_for(eid)] += 1
        # 95% confidence intervals; use generous tolerance for 1k samples.
        assert 600 <= counts["train"] <= 800
        assert 100 <= counts["dev"] <= 200
        assert 100 <= counts["test"] <= 200


class TestPersistence:
    def test_write_dataset_roundtrip(self, tmp_path: Path) -> None:
        chosen = sample_with_constraints(
            generate(seed=42, count=10_000),
            target_count=20,
            min_pass=2,
            min_fail=2,
            min_distinct_procedure_codes=2,
        )
        n = write_dataset(chosen, output_root=tmp_path)
        assert n == 20
        labels = (tmp_path / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(labels) == 20
        encounters = list((tmp_path / "encounters").glob("*.json"))
        assert len(encounters) == 20


class TestNoteText:
    def test_note_has_required_sections(self) -> None:
        for e in _take(iter(generate(seed=42, count=10)), 10):
            note = e.note_text
            assert "CC:" in note
            assert "HPI:" in note
            assert "Exam:" in note
            assert "MDM:" in note
            assert "Procedure:" in note
