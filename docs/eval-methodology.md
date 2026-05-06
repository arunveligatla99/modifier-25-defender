# Eval Methodology

How accuracy and safety are measured for Modifier 25 Defender. Authoritative
threshold values live in `eval/thresholds.yaml`; this document explains
what each metric means and how to interpret a failure.

## Metric catalog

| Metric                                  | Source              | Threshold        | What it measures |
|-----------------------------------------|---------------------|------------------|------------------|
| `retrieval.recall_at_5`                 | AC-002-3            | minimum 0.85     | Fraction of hand-curated retrieval questions whose expected source appears in the top 5 reranked chunks. |
| `retrieval.latency_p95_ms`              | AC-002-5            | maximum 800      | 95th percentile retrieval latency on a single-node Qdrant Docker setup. |
| `parser.field_accuracy`                 | AC-003-2            | minimum 0.90     | Fraction of (encounter, field) pairs where the predicted span covers 80 to 120 percent of the ground-truth span. |
| `parser.latency_p95_seconds`            | AC-003-5            | maximum 5        | Per-encounter parser latency p95. |
| `analyzer.verdict_accuracy`             | AC-004-2            | minimum 0.85     | Fraction of overall verdicts on the test split that match ground truth (PASS-vs-FAIL confusions only). |
| `analyzer.per_criterion_accuracy`       | AC-004-3            | minimum 0.80     | Average per-criterion accuracy across the four JARALL criteria on the test split. |
| `analyzer.faithfulness`                 | AC-004-5 (RAGAS)    | minimum 0.88     | RAGAS faithfulness on analyzer claims. |
| `analyzer.latency_p95_seconds`          | AC-004-6            | maximum 20       | Per-encounter analyzer latency p95 across all four criteria. |
| `compliance_guard.adversarial_recall`   | AC-005-2            | minimum 1.00     | Fraction of fake claims in `data/adversarial/claims.jsonl` correctly flagged. NON-NEGOTIABLE. |
| `compliance_guard.false_positive_rate`  | AC-005-3            | maximum 0.10     | Fraction of ground-truth-correct claims the guard flags. |
| `compliance_guard.latency_p95_seconds`  | AC-005-5            | maximum 3        | Compliance check latency p95 with 8 to 12 citations. |
| `drafter.latency_p95_seconds`           | AC-006-5            | maximum 10       | Drafter latency p95. |
| `drafter.clinical_reasonableness`       | AC-006-4            | minimum 0.80     | Manual review of 20 dev-split suggestions. CPC-trained reviewer ideally. |
| `end_to_end.latency_p95_seconds`        | spec SC-001         | maximum 30       | Composed end-to-end /analyze latency p95. |
| `ui.render_after_response_ms`           | AC-008-1            | maximum 500      | UI render latency after the API call returns. |

## How a CI run works

1. PR triggers `.github/workflows/ci.yml`.
2. The lint, type, em-dash, PHI, and import-graph gates run in parallel
   and must pass before the eval gate runs.
3. The unit-test job runs `pytest tests/unit` with the 80 percent
   coverage threshold.
4. The UI build job runs `npm install` and `npm run build` plus Vitest.
5. The eval gate job runs `uv run python -m eval.run` (which writes a
   timestamped JSON report under `eval/reports/`) followed by
   `uv run python -m eval.check_gates` against the latest report.
6. The threshold-change gate runs only when `eval/thresholds.yaml`
   appears in the PR diff and requires a "Threshold change rationale:"
   block in the PR description.
7. Nightly: `.github/workflows/nightly-eval.yml` runs the full eval
   without the LLM cache, posts a regression issue when any threshold
   fails, and uploads the report as a workflow artifact.

## How to interpret a failure

The gate checker emits one line per violation with the metric path, the
actual value, the bound name, and the threshold. Common failure modes:

- **`retrieval.recall_at_5` minimum violation**: the chunker, embedder,
  or reranker changed in a way that evicted a previously top-5 chunk
  for a question. Rebuild the corpus, re-run `make eval-retrieval`, and
  diff the per-question pass/fail flags.
- **`compliance_guard.adversarial_recall` minimum violation**: the NLI
  model (or its threshold) changed and now entails a hallucinated
  claim. Inspect which claim_id dropped to a passing entailment score;
  consider tightening the threshold or replacing the NLI head.
- **`analyzer.verdict_accuracy` minimum violation**: a per-criterion
  prompt changed in a way that flips PASS-vs-FAIL on the test split.
  Look at the analyzer Langfuse spans for the failing encounters.
- **A `*.latency_p95_seconds` maximum violation**: usually a slow LLM
  call or cache miss. Check the Langfuse trace for the slowest spans.

## How to change a threshold

1. Open a PR that edits `eval/thresholds.yaml`.
2. Include a "Threshold change rationale:" block in the PR description
   with at least 50 characters of justification. Reference the AC source
   and explain why the new threshold is correct.
3. CI's threshold-change gate enforces both the rationale presence and
   length. Reviewer approval is still required.

A constitutional amendment is required when the change weakens
Constitution-driven gates (`compliance_guard.adversarial_recall`, the
em-dash gate, the PHI gate, the import-graph lint). Per Q3 resolution,
quality gates are sacrosanct under schedule pressure.
