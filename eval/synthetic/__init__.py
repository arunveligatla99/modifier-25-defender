"""Synthetic encounter generator (EPIC-001).

The generator is deterministic given a seed (AC-001-6). The default seed is
42 (see ``data/synthetic/seed.txt``). Each encounter has labeled
ground-truth across the four JARALL Standard criteria plus an overall
verdict (AC-001-2).

Modules:

- :mod:`eval.synthetic.parameters` 12-dimension parameter space.
- :mod:`eval.synthetic.templates` slot-fill templates per criterion and
  per procedure type.
- :mod:`eval.synthetic.generator` deterministic generator over the
  parameter space.
- :mod:`eval.synthetic.sampler` stratified sampler enforcing the AC-001
  count constraints.
- :mod:`eval.synthetic.split` deterministic 70/15/15 train/dev/test split.
- :mod:`eval.synthetic.cli` entry point for ``make synthetic-data``.
"""
