# Implementation Plan: Modifier 25 Defender (v1 MVP)

**Branch**: `feature/001-modifier-25-defender` | **Date**: 2026-05-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-modifier-25-defender/spec.md`

## Summary

Implement the v1 Modifier 25 Defender as a four-agent LangGraph pipeline (Documentation Parser, Defensibility Analyzer, Remediation Drafter, Compliance Guard) behind a FastAPI service, with hybrid retrieval (Qdrant dense + BM25 sparse + RRF + cross-encoder rerank) over a 30 to 60 document reference corpus, evaluated by a custom JARALL Standard harness plus RAGAS, and surfaced through a React + Tailwind demo UI. v1 ships local-only via Docker Compose. The Compliance Guard runs NLI entailment on every cited claim and BLOCKS responses that fail; per Q2 resolution the v1 UI is two-state (PASSED, BLOCKED) and the DEGRADED path defined in the source design is deferred to v1.1. Every binding constraint traces back to one of the 47 acceptance criteria (`AC-001-1` through `AC-008-5`) preserved in the spec and to the five core principles in the constitution.

## Technical Context

**Language/Version**: Python 3.11+ (backend, agents, eval). TypeScript 5+ on the UI side (React 18).
**Primary Dependencies**: FastAPI, LangGraph, Pydantic v2, OpenAI Python SDK, Qdrant Python client, `rank_bm25`, `transformers` (cross-encoder + DeBERTa NLI), `ragas`, `langfuse`, `pytest`, `mypy`, `ruff`, `black`. Frontend: React 18, Tailwind CSS, Vite.
**Storage**: PostgreSQL (LangGraph checkpoint persistence + Langfuse self-hosted backend). Qdrant single-node Docker (vector store). On-disk JSON for synthetic data and ground-truth labels under `data/synthetic/`. Reference corpus source files under `data/corpus/`. LLM-call cache under `eval/.cache/` keyed on prompt + retrieval context + model version + temperature (Q5 resolution).
**Testing**: `pytest` for unit and integration. Custom eval harness under `eval/` for retrieval recall@5, defensibility accuracy, compliance guard adversarial recall. RAGAS for faithfulness. CI runs on GitHub Actions; thresholds enforced from `eval/thresholds.yaml`.
**Target Platform**: Local development via Docker Compose (Linux containers; host is Windows 11 + Docker Desktop or any Linux/macOS dev machine). Production deployment is deferred (out of scope for v1).
**Project Type**: Web application with separate backend (Python service + agents) and frontend (React SPA), plus eval harness and synthetic-data tooling.
**Performance Goals**: End-to-end p95 < 30s per encounter (composed of: parser p95 < 5s [AC-003-5], analyzer p95 < 20s [AC-004-6], drafter p95 < 10s [AC-006-5], compliance check p95 < 3s [AC-005-5], retrieval p95 < 800ms [AC-002-5], UI render < 500ms [AC-008-1]).
**Constraints**:
- No real PHI ever (Constitution Principle IV).
- No bypass of the Compliance Guard (Constitution Principle II, AC-005-6).
- Em-dash (U+2014) prohibition on curated text (Q1: option C scope: `app/`, `eval/`, `ui/src/`, `docs/`, `specs/`, `*.md`).
- Quality gates non-bypassable (AC-007-6).
- Reference corpus 30 to 60 documents for v1.
- LLM call budget approximately $200 to $400 over project lifetime (R3 mitigation).
**Scale/Scope**: Single-user demo. 100 synthetic encounters (70/15/15 split). 30 to 60 reference documents (chunked, ~200 to 400 tokens per chunk with 50-token overlap). 30-question retrieval eval set. 20-claim adversarial set for the Compliance Guard. ~6 distinct procedure codes covered. Single-encounter analysis only (no longitudinal).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version evaluated: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle / Constraint | How the plan satisfies it | Evidence |
|---|------------------------|---------------------------|----------|
| I | Citation-First Synthesis | Every `CriterionScore` includes at least one `Citation`; the Compliance Guard rejects empty-evidence outputs. | AC-004-4 in spec; data contract `CriterionScore.evidence: Citation[]`. |
| II | Synthesis and Verification Are Architecturally Separate (NON-NEGOTIABLE) | Compliance Guard lives in `app/agents/compliance_guard/`, separate module from `app/agents/{parser,analyzer,drafter}/`. NLI verification runs on every response (AC-005-6). No bypass flag. | EPIC-005, AC-005-1, AC-005-6. Module boundary enforced by import-graph lint rule (added in tasks). |
| III | No Autonomous Coding Action | System scores existing codes only. Drafter outputs `RemediationSuggestion[]` parallel to source note, never edits it (AC-006-3). No payer/clearinghouse/EHR write integration in scope. | Spec Out of Scope; AC-006-3; data contract has no `note_edit` or `claim_submit` field. |
| IV | Synthetic Data Only (v1) | Generator deterministic with seed=42 (Q4 resolution). No real PHI assumption stated. CI gate added in EPIC-007 to grep for PHI markers (real names, real DOBs) in fixtures. | AC-001-6; spec Assumptions; data/synthetic/seed.txt. |
| V | Full Auditability and Replay | Every `DefenderResponse` carries `trace_id` linking to Langfuse trace. LangGraph state persisted to Postgres for replay. | Data contract `DefenderResponse.trace_id`; SC-005. |
| TS | Tech Stack | Plan commits to Python 3.11+, FastAPI, LangGraph, Pydantic v2, Qdrant, BM25, cross-encoder rerank, DeBERTa NLI, Langfuse, React 18 + Tailwind + Vite, Docker Compose, GitHub Actions, RAGAS. Matches constitution verbatim. | Technical Context above. |
| CS-1 | Type safety: Pydantic v2 + strict mypy on `app/` | Pydantic v2 used for every data contract. `pyproject.toml` configures mypy strict mode on the `app` package. CI runs `mypy app/`. | Tasks T-mypy-strict (in tasks.md). |
| CS-2 | Google-style docstrings on public APIs | Linter rule added (`ruff` `D` rules subset, Google convention). CI fails on undocumented public symbols. | Tasks T-ruff-docstrings. |
| CS-3 | Em-dash prohibition (U+2014) | CI gate greps changed files in scoped paths (Q1: option C scope). | Tasks T-ci-emdash. |
| CS-4 | `ruff` + `black` enforced in CI | Both tools wired into the GitHub Actions workflow. | Tasks T-ci-lint, T-ci-format. |
| TD-1 | Unit tests on every new agent / retrieval / schema module | Each agent module has a paired `tests/unit/test_<module>.py`. PR description template includes a unit-test checklist. | Tasks (per-EPIC test tasks). |
| TD-2 | 80% coverage on `app/` excluding I/O glue | `pyproject.toml` `[tool.coverage]` config excludes `app/api/main.py`, `app/db/session.py`, `app/infra/*`. CI fails below 80%. | Tasks T-ci-coverage. |
| TD-3 | E2E gated by eval harness with PR-blocking thresholds | `eval/thresholds.yaml` ships with all thresholds from AC-002-3, AC-004-2, AC-004-3, AC-005-2, AC-004-5. CI workflow runs harness and fails on regression. | Tasks T-ci-eval-gate. |

**Result**: PASS. No constitution violations require justification. Complexity Tracking section below is empty.

(Re-checked after Phase 1 design: still PASS. The data model and contracts produced in Phase 1 do not introduce any new violations; see Phase 1 outputs.)

## Project Structure

### Documentation (this feature)

```text
specs/001-modifier-25-defender/
├── plan.md                    # This file (/speckit-plan output)
├── spec.md                    # /speckit-specify output
├── research.md                # Phase 0 output
├── data-model.md              # Phase 1 output
├── quickstart.md              # Phase 1 output
├── contracts/                 # Phase 1 output
│   └── analyze-endpoint.md    # FastAPI POST /analyze contract
├── tasks.md                   # Phase 2 output (/speckit-tasks - NOT created here)
├── analyze-report.md          # /speckit-analyze output (deferred)
└── checklists/
    └── requirements.md        # spec quality checklist
```

### Source Code (repository root)

Web application layout: `app/` (backend, agents, retrieval, schemas, API), `ui/` (React frontend), `eval/` (harness), `data/` (synthetic + corpus), `infra/` (Docker Compose), `prompts/` (versioned agent prompts), `docs/` (architecture, methodology, limitations), `tests/` (unit + integration), `.github/workflows/` (CI).

```text
modifier-25-defender/
├── app/
│   ├── agents/
│   │   ├── orchestrator/         # LangGraph wiring + DefenderSession state
│   │   ├── parser/               # Documentation Parser (EPIC-003)
│   │   ├── analyzer/             # Defensibility Analyzer (EPIC-004)
│   │   ├── drafter/              # Remediation Drafter (EPIC-006)
│   │   └── compliance_guard/     # Compliance Guard (EPIC-005), separate module
│   ├── retrieval/                # Qdrant + BM25 + RRF + reranker (EPIC-002)
│   ├── api/                      # FastAPI service (POST /analyze)
│   ├── schemas/                  # Pydantic v2 data contracts
│   ├── llm/                      # OpenAI client wrapper + content-hash cache
│   ├── observability/            # Langfuse client + trace_id helpers
│   └── infra/                    # DB session, settings, env loading
├── data/
│   ├── synthetic/                # Generated encounters + ground-truth labels
│   │   ├── encounters/
│   │   ├── labels.jsonl
│   │   └── seed.txt              # seed = 42
│   ├── corpus/                   # CMS, AAPC, JARALL source documents
│   └── retrieval_eval/           # 30-question retrieval eval set
├── eval/
│   ├── retrieval/                # Recall@5 harness
│   ├── defensibility/            # Verdict and per-criterion accuracy harness
│   ├── adversarial/              # 20-claim hallucination test set + harness
│   ├── faithfulness/             # RAGAS integration
│   ├── thresholds.yaml           # AC-002-3, AC-004-2, AC-004-3, AC-005-2, AC-004-5
│   ├── .cache/                   # content-hash LLM call cache (gitignored)
│   └── reports/                  # generated eval reports
├── ui/
│   ├── src/
│   │   ├── components/           # CriterionCard, CitationLink, BlockedBanner, etc.
│   │   ├── pages/                # /analyze, /quality
│   │   ├── api/                  # typed client for POST /analyze
│   │   └── styles/               # Tailwind config + custom CSS
│   ├── tests/                    # Vitest unit tests on UI components
│   └── package.json
├── infra/
│   ├── docker-compose.yaml       # Qdrant, Postgres, Langfuse, Backend, UI
│   └── Dockerfile.backend, Dockerfile.ui
├── prompts/                      # versioned agent prompts (Markdown + JSON schema)
│   ├── parser/v1.md
│   ├── analyzer/{distinct_cc,separate_exam,independent_mdm,site_specificity}/v1.md
│   └── drafter/v1.md
├── tests/
│   ├── unit/                     # mirrors app/ tree
│   └── integration/              # cross-agent e2e on a few synthetic encounters
├── docs/
│   ├── SPEC_DRIVEN_DEVELOPMENT.md  # already in repo
│   ├── architecture.md
│   ├── eval-methodology.md
│   ├── synthetic-data.md
│   └── limitations.md
├── .github/workflows/
│   ├── ci.yml                    # lint, type, test, eval-gate, em-dash check
│   └── nightly-eval.yml          # full eval against main, posts report
├── pyproject.toml                # uv + ruff + black + mypy + pytest + coverage
├── Makefile                      # `make corpus`, `make synthetic-data`, `make eval`, `make dev`
├── .env.example
└── README.md                     # project README (already in repo)
```

**Structure Decision**: web application layout (Option 2 from spec-kit's plan template, expanded). Separation of `app/agents/compliance_guard/` from the synthesis-side agents is load-bearing for Constitution Principle II and is enforced by an import-graph lint rule (added in tasks). The eval harness lives in `eval/` (sibling of `app/`) so it can import production code while remaining out of scope for runtime imports.

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| (none)    | (n/a)      | (n/a)                                |
