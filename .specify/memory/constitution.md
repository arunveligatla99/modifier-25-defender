<!--
SYNC IMPACT REPORT (constitution amendment)

Version change: (none) -> 1.0.0
Bump rationale: Initial ratification. No prior version. Establishes binding principles, tech stack and coding standards, testing discipline, development workflow, and governance.

Modified principles:
  (none, this is the initial ratification)

Added sections:
  - Core Principles (5 principles)
      I. Citation-First Synthesis
      II. Synthesis and Verification Are Architecturally Separate (NON-NEGOTIABLE)
      III. No Autonomous Coding Action
      IV. Synthetic Data Only (v1)
      V. Full Auditability and Replay
  - Tech Stack, Coding Standards, and Testing Discipline
  - Development Workflow
  - Governance
  - Open Questions (deferred items pending explicit user confirmation)

Removed sections:
  (none)

Templates requiring updates (consistency propagation):
  - .specify/templates/plan-template.md       OK no change required (Constitution Check section is generic; gates are read from this file at /speckit-plan time)
  - .specify/templates/spec-template.md       OK no change required (no hardcoded principle references; constitution-driven constraints are surfaced by /speckit-plan, not the spec)
  - .specify/templates/tasks-template.md      OK no change required (task categorization is feature-driven; observability and verification appear in this constitution, but the template itself is generic)
  - .specify/templates/checklist-template.md  OK no change required
  - .claude/skills/speckit-*/SKILL.md         OK no change required (agent-neutral skill content, does not reference principles by name)
  - README.md (project)                       OK aligned (this constitution is referenced from the project README and the SDD workflow doc added in Phase 5)

Follow-up TODOs:
  - TODO(BRANCH_NUMBERING_CONFIRM): user accepted defaults at intake, branch numbering strategy is sequential by spec-kit default; explicit confirmation deferred
  - TODO(LICENSE_PUBLIC_CONFIRM): MIT chosen by default, confirm before first public push
  - TODO(GH_REMOTE): GitHub remote creation deferred to Phase 7 of bootstrap
-->

# Modifier 25 Defender Constitution

## Project Purpose

Modifier 25 Defender is a documentation defensibility tool for podiatry coders, built on the JARALL Standard. It is an agentic AI system that ingests a podiatry encounter note alongside its E/M code, procedure code, and Modifier 25 attachment, and produces a structured defensibility assessment with cited rationale and targeted remediation language for human coder review. Every claim the system makes is grounded in retrieved source text and verified by a separate compliance agent before reaching the user. The system never modifies the source note, never assigns codes, and never submits claims; it scores, cites, and suggests for human review.

## Core Principles

### I. Citation-First Synthesis

Every model output MUST cite the source sentences that support it. Empty-evidence outputs are a hard failure, not a degraded mode. Every `CriterionScore` MUST include at least one `Citation`; the Compliance Guard rejects responses with unsupported claims. UI elements that present a score MUST expose the supporting citation(s) inline or one click away. No claim may be shown to the user without a verifiable source.

**Rationale**: Defensibility tooling that cannot cite its evidence is itself indefensible. The product's value to a coder is precisely the audit trail; without citations the output is opinion, not defense.

### II. Synthesis and Verification Are Architecturally Separate (NON-NEGOTIABLE)

The agent that produces output is NOT the agent that verifies output. The Compliance Guard runs after the synthesis path on every response and uses NLI entailment checking against retrieved evidence. There is NO bypass flag. The Compliance Guard MUST run on every response, never sampled. If any cited claim fails entailment on a FAIL criterion verdict the response MUST be BLOCKED. Verification logic MUST live in a separate module from the synthesis agents and MUST NOT share prompts, models, or state with them beyond the explicit handoff.

**Rationale**: Synthesis-side failures cannot self-detect; only an independent verifier breaks that loop. This pattern is non-negotiable in v1 and any future version. Removing or weakening it constitutes a breaking constitutional amendment (MAJOR version bump).

### III. No Autonomous Coding Action

The system never assigns CPT, ICD-10, HCPCS, or modifier codes. It scores documentation supporting an existing code; it does not propose codes. It never edits the source note: remediation appears as parallel suggestions in a separate UI panel marked for clinician review. It never submits claims. It MUST NOT have payer, clearinghouse, or EHR write integration, and MUST NOT be designed to acquire one. UI MUST render remediation suggestions distinctly from the source note (separate panel, distinct visual treatment), with explicit accept/modify/reject affordances reserved for the human user.

**Rationale**: Human-in-the-loop is the safety boundary; autonomy here would create medico-legal and compliance risk the system cannot mitigate. The product is an advisor, not an actor.

### IV. Synthetic Data Only (v1)

No real PHI in any commit, ever, including deleted commits and historical branches. All encounter data in v1 MUST be programmatically generated with a fixed, documented seed (default seed: 42). The system has not been validated on real PHI and is NOT HIPAA-compliant for real-PHI processing. HIPAA-compliant real-PHI processing is a v2 commitment behind a Business Associate Agreement, validated controls, and a separate spec; it is not a v1 stretch goal. PR review MUST refuse any change that introduces a fixture, sample, or test input that could plausibly be a real encounter (real names, real DOBs, real addresses, real MRNs).

**Rationale**: Shipping a defensibility tool that handles real PHI without a BAA and validated controls is itself a compliance violation. The synthetic-only constraint protects users, the project, and the maintainer from a regulatory failure that would invalidate the product on day one.

### V. Full Auditability and Replay

Every agent decision MUST be logged to Langfuse with the inputs, retrieved sources, agent state, and output. Every `DefenderResponse` MUST carry a `trace_id` linking to its Langfuse trace. Replay MUST be supported: given a `trace_id`, an engineer can reproduce the decision path with the same inputs and retrieved context. Logs MUST be retained for the demo lifetime; production retention policy is deferred to v2 alongside the BAA work.

**Rationale**: A tool that cannot show its work cannot be audited, and a compliance tool that cannot be audited cannot be trusted. Replay also makes regression analysis tractable: when an eval threshold drops, the team can step through the failing trace rather than guessing.

## Tech Stack, Coding Standards, and Testing Discipline

### Tech Stack Commitments

- **Language and runtime**: Python 3.11+ for the backend. Package manager: `uv`.
- **Backend framework**: FastAPI for the HTTP API.
- **Agent orchestration**: LangGraph with typed state, conditional routing, and persistence to PostgreSQL.
- **Data contracts**: Pydantic v2 for every type that crosses an agent or API boundary.
- **LLM**: OpenAI GPT-4o for synthesis agents; `text-embedding-3-large` for dense retrieval.
- **Retrieval**: Qdrant (single-node Docker for v1) for dense vectors; BM25 for sparse; Reciprocal Rank Fusion (k=60) for combination; cross-encoder rerank (`BAAI/bge-reranker-v2-m3` or equivalent).
- **Verification**: DeBERTa-v3-large-mnli (or equivalent) for NLI entailment, local CPU inference, no third-party API call.
- **Observability**: Langfuse self-hosted.
- **UI**: React 18 + Tailwind + Vite. Single-page app. No auth in v1.
- **Local infrastructure**: Docker Compose. Cloud deployment is deferred; v1 ships local-only.
- **CI**: GitHub Actions with PR-blocking quality gates. No advisory mode.
- **Eval**: RAGAS plus a custom JARALL Standard eval harness.

Substitution of any of the above requires a constitutional amendment (PATCH for in-kind swap of an equivalent library, MINOR for a category change, MAJOR if a load-bearing principle is affected).

### Coding Standards

- **Type safety**: Pydantic v2 for every data contract crossing an agent or API boundary. Strict `mypy` on the `app/` package; CI fails on `mypy` errors.
- **Public API documentation**: Google-style docstrings on every public function, class, and module in `app/`, `eval/`, and `ui/api` modules.
- **Em-dash prohibition**: the em-dash character (Unicode code point U+2014) MUST NOT appear in any documentation, spec, code comment, commit message, PR description, README, or other generated text in this project. Use commas, periods, colons, parentheses, or rephrase. CI MUST grep for U+2014 in changed files and fail on any match. This is non-negotiable.
- **Linting and formatting**: `ruff` for linting; `black` for formatting. CI enforces both. Auto-fix on save is recommended for local dev.
- **Imports and module layout**: prefer absolute imports under `app.` paths; no relative imports across package boundaries.

### Testing Discipline

- **Framework**: `pytest`.
- **Unit tests**: every new agent module under `app/agents/`, every retrieval module under `app/retrieval/`, and every Pydantic schema under `app/schemas/` MUST have unit tests added in the same PR. New code without unit tests is a PR-blocking review failure.
- **Coverage**: 80% line coverage on `app/`, excluding pure I/O glue (database connection setup, FastAPI route registration, infrastructure boilerplate). Coverage thresholds enforced in CI.
- **End-to-end correctness**: gated by the eval harness, not by mock data alone. The following thresholds MUST be enforced in CI and are PR-blocking:
  - Retrieval recall@5 >= 0.85
  - Overall verdict accuracy >= 0.85 on the test split
  - Per-criterion accuracy >= 0.80 averaged across the four JARALL Standard criteria
  - Compliance Guard recall = 1.00 on the adversarial set
  - RAGAS faithfulness >= 0.88
  - End-to-end latency p95 < 30 seconds
- Threshold values live in `eval/thresholds.yaml`. Changing any threshold requires a PR with rationale in the description and reviewer acceptance; no silent loosening.

## Development Workflow

### Spec-Driven Development Commitment

- Every feature starts with `/speckit-specify`. No source code in `app/`, `eval/`, or `ui/` may be added without an approved spec under `specs/<NNN-slug>/`.
- Configuration files, test fixtures, and infrastructure manifests (Docker Compose, CI workflows, `.gitignore`, `pyproject.toml`, etc.) MAY be added without a spec.
- The spec, plan, and tasks artifacts under `specs/<NNN-slug>/` are the authoritative description of work.
- The source documents in the parent directory (`Modifier25_Defender_Spec.docx`, `Modifier25_Defender_OnePager.docx`, `JARALL_EHR_Integration_Brief.docx`) are the v1 design intent. They are referenced from the specs but MUST NOT be edited as part of feature work; if the design intent itself changes, that is a separate change captured in a new revision of the source document and reflected in a fresh spec.

### Branching and Review

- Branch naming: `feature/<NNN>-<slug>` matching the spec directory.
- Branch numbering strategy: sequential (`001`, `002`, ...). See Open Questions for the deferred explicit confirmation.
- PR review required even for solo work. Self-review with a 24-hour cool-off period satisfies this for the solo phase.
- CI quality gates are PR-blocking and MUST NOT be bypassed (`--no-verify`, force-push to main, admin merge override are all forbidden).

### Workflow Sequencing for Each Feature

1. `/speckit-specify` produces `specs/<NNN-slug>/spec.md`.
2. `/speckit-clarify` (optional) surfaces underspecified areas and folds answers back into `spec.md`.
3. `/speckit-plan` produces `plan.md` and the supporting design artifacts; the Constitution Check gate in the plan template MUST be evaluated against this file.
4. `/speckit-tasks` produces `tasks.md`.
5. `/speckit-analyze` (optional but recommended for first feature) produces a cross-artifact consistency report; remaining issues MUST be addressed or explicitly accepted before implementation begins.
6. `/speckit-implement` executes against `tasks.md`. Quality gates MUST pass before merge.

## Governance

This constitution supersedes ad-hoc practice. All PRs MUST verify compliance with these principles. Complexity that violates a principle MUST be justified in the PR description and accepted by a reviewer; absent justification, the PR is rejected.

**Amendment procedure**: amendments require a PR that updates `.specify/memory/constitution.md`, increments the version per semver, updates the Last Amended date, includes a Sync Impact Report at the top of the file as an HTML comment, and propagates any necessary updates to dependent templates and runtime guidance. Versioning rules:
- **MAJOR**: backward-incompatible removal or redefinition of a principle (for example, weakening or removing the Compliance Guard separation).
- **MINOR**: addition of a new principle or section, or material expansion of an existing principle's scope.
- **PATCH**: clarifications, wording, typo fixes, non-semantic refinements.

**Versioning policy**: semantic versioning applied to this document, independent of the project's release version.

**Compliance review**: every `/speckit-plan` run MUST evaluate the plan against this constitution at the Constitution Check gate; violations block the plan until justified or revised. Every `/speckit-implement` run inherits the same constraints transitively through the approved plan.

**Runtime guidance**: this file plus `docs/SPEC_DRIVEN_DEVELOPMENT.md` (added in Phase 5 of bootstrap) are the runtime guidance for contributors and agents.

## Open Questions

The following items were accepted as defaults at project intake and remain open for explicit user confirmation. They are tracked here so they are not lost; resolving any of them is a PATCH amendment.

- TODO(BRANCH_NUMBERING_CONFIRM): branch numbering strategy is sequential by spec-kit default; the user accepted defaults at intake but has not yet explicitly chosen between sequential and timestamp.
- TODO(LICENSE_PUBLIC_CONFIRM): LICENSE chosen as MIT by default; confirm before first public push.
- TODO(GH_REMOTE): GitHub remote creation deferred to Phase 7 of bootstrap; confirm whether the repo is created publicly or kept private at first.

**Version**: 1.0.0 | **Ratified**: 2026-05-03 | **Last Amended**: 2026-05-03
