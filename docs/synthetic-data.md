# Synthetic data

Modifier 25 Defender uses synthetic data exclusively in v1 (Constitution
Principle IV). This document describes how encounters are generated,
labeled, and split.

## Generator entry point

```bash
make synthetic-data           # generates 100 encounters at seed=42
uv run python -m eval.synthetic.cli generate --seed 42 --count 100
```

Output:

- `data/synthetic/encounters/synth_<index>_<hash>.json`: one file per
  generated encounter. Pydantic-serialized `SyntheticEncounter` model.
- `data/synthetic/labels.jsonl`: one record per encounter with the
  encounter_id, split, ground-truth labels, and codes.

## Parameter space (12 dimensions)

| Dimension                        | Values |
|----------------------------------|--------|
| `presenting_condition`           | thick_painful_nails, callus_pain, heel_pain, plantar_fasciitis_followup, diabetic_foot_check, ankle_arthritis_flare, hallux_pain, ingrown_toenail (8) |
| `diabetes`                       | bool (P=0.4) |
| `neuropathy`                     | bool (P=0.3) |
| `pvd`                            | bool (P=0.2) |
| `procedure_type`                 | nail_debridement_few/many, callus_paring_single/few/many, joint_injection (6) |
| `site`                           | L, R, B, None (4) |
| `em_level`                       | 99212, 99213, 99214, 99215 (4) |
| `separable_problem`              | bool (P=0.5) |
| `site_specificity_stated`        | bool (P=0.5) |
| `mdm_separability`               | none, low, medium, high (4) |
| `exam_separability`              | none, low, medium, high (4) |
| `narrative_style`                | terse, standard, verbose (3) |

Sampling is uniform over the parameter space. The bucketed stratified
sampler over-generates by 100x and selects 100 encounters meeting the
AC-001 minimums.

## Ground-truth labels

Each encounter gets:

- Per-criterion verdict (`distinct_cc`, `separate_exam`,
  `independent_mdm`, `site_specificity`).
- Overall verdict (deterministic aggregate per spec EPIC-004 7.2).
- `parameter_space_index` recording which slot was chosen for each of
  the 12 dimensions.

Label rules live in `eval/synthetic/templates.py` and are deterministic
given the parameter-space point. Reference rules:

- `distinct_cc = PASS` iff `separable_problem`.
- `separate_exam` and `independent_mdm` map separability levels to
  verdicts: `high -> PASS`, `medium -> WEAK`, `low/none -> FAIL`.
- `site_specificity = PASS` when E/M and procedure are at different
  sites with modifiers documented; WEAK when sites differ but no
  modifier; FAIL when same-site without separable problem.

## Train/dev/test split (AC-001-8)

Split membership is deterministic on a SHA1 hash of the encounter_id:

- bucket < 70: train
- 70 <= bucket < 85: dev
- 85 <= bucket: test

Splits are stable across regenerations because the encounter_id itself
is stable on a given seed and parameter-space point.

## Reproducibility

Re-run `make synthetic-data` from a fresh clone with seed=42. The output
is byte-for-byte identical given a stable Python version (the seed
determines the random walk; the templates are pure functions of the
parameter point).

## Manual review (AC-001-7, T107)

A 20-encounter manual review pass catches generator drift. The review
checks for contradictory exam findings, anatomically impossible
procedures, and other unrealism. The review notes land at
`docs/synthetic-data-review-week1.md` (created when the review runs).
Drift exceeding 10 percent triggers template iteration.

## Adding new dimensions

To extend the parameter space, edit `eval/synthetic/parameters.py` and
the templates in `eval/synthetic/templates.py`. The label functions
must remain deterministic given a parameter-space point. The
`parameter_space_index` will pick up the new dimensions automatically.
