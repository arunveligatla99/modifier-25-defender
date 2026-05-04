"""CLI entry point for ``make synthetic-data``.

Generates the configured number of synthetic encounters with the configured
seed, persists each encounter as JSON under ``data/synthetic/encounters/``,
and writes the labels file at ``data/synthetic/labels.jsonl``.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

from eval.schemas import SyntheticEncounter
from eval.synthetic.generator import generate
from eval.synthetic.sampler import sample_with_constraints

DEFAULT_OUTPUT_ROOT = Path("data/synthetic")


def write_dataset(
    encounters: Iterable[SyntheticEncounter],
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> int:
    """Persist a list of synthetic encounters and return the count written."""
    encounters_dir = output_root / "encounters"
    encounters_dir.mkdir(parents=True, exist_ok=True)
    labels_path = output_root / "labels.jsonl"

    count = 0
    with labels_path.open("w", encoding="utf-8", newline="\n") as labels_fh:
        for encounter in encounters:
            count += 1
            (encounters_dir / f"{encounter.encounter_id}.json").write_text(
                encounter.model_dump_json(indent=2),
                encoding="utf-8",
                newline="\n",
            )
            label_record = {
                "encounter_id": encounter.encounter_id,
                "split": encounter.split,
                "ground_truth": encounter.ground_truth.model_dump(),
                "em_code": encounter.em_code,
                "procedure_code": encounter.procedure_code,
            }
            labels_fh.write(json.dumps(label_record, sort_keys=True) + "\n")
    return count


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="eval.synthetic.cli",
        description="Generate the synthetic encounter dataset (AC-001-*).",
    )
    parser.add_argument(
        "command",
        choices=["generate"],
        help="Subcommand. Currently only 'generate' is supported.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Generator seed (default: 42)")
    parser.add_argument("--count", type=int, default=100, help="Number of encounters to write")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Output root (default: data/synthetic/)",
    )
    args = parser.parse_args(argv)

    if args.command != "generate":  # pragma: no cover - argparse handles this
        parser.error(f"unsupported command {args.command!r}")

    # Over-generate so the sampler has slack to satisfy AC-001-3/4/5. The
    # uniform random walk over the parameter space yields roughly 1 to 2
    # percent overall=PASS encounters, so we need ~50x the target count to
    # have headroom for the PASS minimum.
    candidates = generate(seed=args.seed, count=max(args.count * 100, 10_000))
    chosen = sample_with_constraints(candidates, target_count=args.count)
    written = write_dataset(chosen, output_root=args.output_root)
    print(
        f"wrote {written} encounters to {args.output_root}/encounters/ "
        f"and labels to {args.output_root}/labels.jsonl"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
