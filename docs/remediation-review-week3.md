# Drafter Clinical Reasonableness Review (T205, AC-006-4)

The Drafter outputs language suggestions for any WEAK or FAIL criterion
the Defensibility Analyzer surfaces. AC-006-4 requires that at least
80% of suggestions on a 20-sample dev-split set be judged clinically
reasonable by a CPC-trained reviewer. Spec language allows careful
self-review against the source policies as a fallback when no CPC
reviewer is available.

## How to refresh the sample

```
uv run python -m eval.run --refresh-drafter-sample \
    --skip-retrieval --skip-guard --skip-parser \
    --skip-defensibility --skip-faithfulness
```

This walks dev-split encounters whose ground-truth overall verdict is
not PASS, runs parser + analyzer + drafter, and writes 20 records to
`data/drafter_review/dev_sample.jsonl`. Each record carries the
`sample_id`, the `criterion`, the `note_text`, the
`suggested_addition`, and the `motivation_citations`.

## How to score

Score each sample by writing one JSON object per line to
`data/drafter_review/scores.jsonl`:

```
{"sample_id": "...", "reasonable": true|false, "notes": "..."}
```

A suggestion is reasonable when:

- It targets the criterion the drafter flagged.
- The language is clinician-facing and plausible.
- The cited policy chunk supports the suggestion.
- It does not fabricate facts that contradict the encounter.

Generic-but-actionable suggestions (e.g., "consider documenting skin
findings beyond the procedure site") are reasonable when they tie to
the encounter's procedure type. Fabrications (e.g., "evaluate
mobility concerns" when the encounter does not mention mobility) and
category mismatches (e.g., calling a comorbidity an anatomic site)
are not reasonable.

## How the metric is computed

`eval.drafter.clinical_reasonableness.evaluate_clinical_reasonableness`
reads `scores.jsonl` and reports
`reasonable_count / total_scored`. The eval orchestrator surfaces this
under `drafter.clinical_reasonableness` in the report. Threshold: 0.80
(`eval/thresholds.yaml`).

When the scores file is absent, the metric stays at 0.0 and the gate
fails. Re-running the harness regenerates the dev sample but does NOT
overwrite scores; reviewers can keep their judgments across drafter
prompt revisions.

## Current self-review (2026-05-04)

- Total scored: 20
- Reasonable: 17
- Rate: 0.85 (>= 0.80, gate passes)

Three samples were marked unreasonable:

- `synth_0006_2a482e69::distinct_cc::0`: fabricates "mobility/daily
  activities" as the distinct CC; the encounter mentions a different
  separable problem.
- `synth_0012_67434f8a::distinct_cc::0`: generic template that does
  not tie to any specific symptom.
- `synth_0017_bec9990b::site_specificity::2`: category mismatch.
  Neuropathy and PVD are conditions, not anatomic sites; the
  site-specificity criterion is about LT/RT modifiers across distinct
  feet/toes.

Next iteration on the drafter prompt should anchor each suggestion to
a specific encounter span and reject site-specificity claims that do
not name a distinct anatomic structure.
