# Quickstart: Modifier 25 Defender (v1 MVP)

**Feature**: `001-modifier-25-defender`
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

This quickstart is the fast path for an engineer (or the maintainer returning to the project) to bring v1 up locally and verify the eval harness end-to-end. It mirrors the `Quick start` section of the project README at a more operational level.

## Prerequisites

- Python 3.11+ (verified: `python --version`)
- `uv` 0.11+ (verified: `uv --version`)
- Docker Desktop or Docker Engine + Docker Compose v2+ (verified: `docker compose version`)
- Node.js 20+ (verified: `node --version`)
- An OpenAI API key with access to GPT-4o and `text-embedding-3-large`
- ~2 GB free disk for Qdrant + Postgres + Langfuse images, plus model weights for the cross-encoder and the NLI head (~2 GB combined)

## First-time setup

```bash
# 1. From the parent directory (JARALL_MM/), enter the project
cd modifier-25-defender

# 2. Configure environment
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, leave other values at defaults

# 3. Install Python dependencies into a project-local venv
uv sync

# 4. Bring up infrastructure (Qdrant, Postgres, Langfuse)
docker compose -f infra/docker-compose.yaml up -d

# 5. Install UI dependencies
cd ui && npm install && cd ..

# 6. Build the reference corpus and index
make corpus

# 7. Generate synthetic encounters (deterministic, seed=42)
make synthetic-data

# 8. Run the eval harness end-to-end
make eval
```

Expected setup time on a clean machine: ~10 minutes including Docker pulls and corpus indexing. `make eval` adds ~5 minutes the first time (LLM cache cold) and <1 minute on subsequent runs (cache warm, per R7).

## Daily development loop

```bash
# In one terminal: backend dev server with hot reload
make dev

# In a second terminal: UI dev server
cd ui && npm run dev

# In a third terminal: run unit tests
uv run pytest tests/unit -v

# Targeted eval after a prompt or retrieval change
make eval-retrieval     # just the recall@5 eval (fast)
make eval-defensibility # just the verdict accuracy eval
make eval-adversarial   # just the Compliance Guard adversarial recall
```

## Verifying acceptance criteria

After `make eval`, the harness writes a report under `eval/reports/<timestamp>.json` with the following keys, each tied to a spec acceptance criterion:

| Report key                | Spec AC      | Threshold |
|---------------------------|--------------|-----------|
| `retrieval.recall_at_5`   | AC-002-3     | >= 0.85   |
| `parser.field_accuracy`   | AC-003-2     | >= 0.90   |
| `analyzer.verdict_accuracy` | AC-004-2   | >= 0.85   |
| `analyzer.per_criterion_accuracy` | AC-004-3 | >= 0.80 (averaged) |
| `analyzer.faithfulness`   | AC-004-5     | >= 0.88   |
| `compliance_guard.adversarial_recall` | AC-005-2 | = 1.00 |
| `compliance_guard.false_positive_rate` | AC-005-3 | <= 0.10 |
| `latency.parser_p95_seconds` | AC-003-5 | < 5      |
| `latency.analyzer_p95_seconds` | AC-004-6 | < 20    |
| `latency.compliance_p95_seconds` | AC-005-5 | < 3   |
| `latency.drafter_p95_seconds` | AC-006-5 | < 10    |
| `latency.retrieval_p95_ms` | AC-002-5    | < 800    |

Any threshold violation is a CI failure on a PR; the same `make eval` invocation runs in `.github/workflows/ci.yml` (per R9).

## Reading a trace in Langfuse

```bash
# After running an /analyze call, open the Langfuse UI
open http://localhost:3000  # or visit in browser
# Find the trace by trace_id from the DefenderResponse
```

Each trace contains the parser, analyzer (4 sub-traces), drafter (if invoked), and compliance guard spans, with inputs and outputs at each step. Replay support: any trace can be re-executed against the current code by `make replay TRACE_ID=lf_t_...`.

## Tearing down

```bash
# Stop infra containers (preserves volumes)
docker compose -f infra/docker-compose.yaml down

# Stop and wipe volumes (forces fresh DB on next up)
docker compose -f infra/docker-compose.yaml down -v
```

## Troubleshooting

- **`make corpus` fails with "Qdrant not reachable"**: Qdrant container is still warming up. Wait ~10 seconds and retry. If persistent, check `docker compose logs qdrant`.
- **PR fails with "em-dash detected" in CI**: a U+2014 character snuck into a curated file. Run `make check-emdash` locally to find it. The check scope is in [research.md R10](./research.md).
- **PR fails with "RAGAS faithfulness below threshold"**: check the analyzer prompts and retrieval context. RAGAS scores are in `eval/reports/<timestamp>.json` under `analyzer.faithfulness_per_encounter`. Look for outliers; they usually signal a retrieval miss for that specific encounter.
- **Latency p95 over budget**: open the corresponding trace in Langfuse and look for slow LLM calls (most often the analyzer's per-criterion calls). Cache warm-up resolves most repeat-eval slowness.
