# Modifier 25 Defender

> A documentation defensibility tool for podiatry coders, built on the JARALL Standard.
> Production-grade agentic AI with citation-first synthesis and an independent compliance guard.

[![CI](https://github.com/arunveligatla/modifier-25-defender/actions/workflows/ci.yml/badge.svg)](https://github.com/arunveligatla/modifier-25-defender/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## What this is, in one paragraph

In 2026, payers use AI to flag every E/M paired with a minor procedure. Practices using Modifier 25 on more than 50% of procedural claims face Pre-Payment Reviews. **Modifier 25 Defender** reads a podiatry encounter note alongside its E/M code, procedure code, and Modifier 25 attachment, and scores defensibility against the four criteria of the JARALL Standard: distinct chief complaint, separate exam findings, independent medical decision making, and site-specificity. Every score is grounded in cited evidence from CMS, AAPC, and JARALL guidance. A separate verification layer blocks any unsupported claim before it reaches the coder.

The system **never modifies notes, never assigns codes, never submits claims**. It scores, cites, and suggests. Coders accept, modify, or reject.

> [!IMPORTANT]
> **No PHI, ever.** All encounter data in this repository is synthetic. The system is designed for synthetic data only and is not currently HIPAA-compliant for production PHI processing. See [Limitations](#limitations).

---

## Quick example

A coder receives an encounter coded `99213 + 11721 + Modifier 25`:

```
CC: thick painful nails
HPI: 6 months of nail thickening and discomfort
Exam: nails L1-L5, R1-R5 thickened with subungual debris
MDM: discussed risks/benefits of debridement, patient consents
Procedure: 10 nails debrided with sterile technique
```

Defender returns in ~20 seconds:

| Criterion           | Verdict | Evidence                                              |
|---------------------|---------|-------------------------------------------------------|
| Distinct CC         | FAIL    | CC is the procedure indication, not a separate problem |
| Separate exam       | FAIL    | Exam findings are limited to the procedure site       |
| Independent MDM     | FAIL    | MDM is procedure workup, not a separate decision      |
| Site-specificity    | N/A     | Same-site E/M and procedure                           |
| **Overall**         | **FAIL** | High confidence (0.94)                               |

It also drafts targeted documentation language the clinician could add (with policy citations), in a separate panel marked clearly as **suggestions for review**, never auto-applied.

---

## Why this exists

JARALL Medical Management's [April 23, 2026 article](https://www.jarallmedical.com/blog/modifier-25-mastery) named the problem directly. Payer AI is increasingly aggressive on Modifier 25. Coders spend significant time defending claims that should have been documented defensibly the first time. This system gives coders a fast, audit-ready second opinion before the claim leaves the practice.

The architecture is the same pattern I shipped at ModMed for clinical policy retrieval (PolicyMind), adapted to revenue cycle and operationalized against a published clinical standard.

---

## Architecture

Four agents in a LangGraph pipeline plus an independent verification layer.

```
                 ┌──────────────────────────────────────────────────────┐
   DefenderRequest                                                       │
   (note, codes,    ┌─────────────────┐                                  │
    Mod 25 site) ──▶│  Orchestrator   │                                  │
                    └────────┬────────┘                                  │
                             │                                           │
                             ▼                                           │
                    ┌─────────────────┐                                  │
                    │  Documentation  │                                  │
                    │     Parser      │                                  │
                    └────────┬────────┘                                  │
                             │  ParsedEncounter                          │
                             ▼                                           │
                    ┌─────────────────┐    Hybrid retrieval              │
                    │  Defensibility  │◀───(Qdrant + BM25 + RRF +        │
                    │    Analyzer     │    cross-encoder rerank)         │
                    └────────┬────────┘                                  │
                             │  DefensibilityAssessment                  │
                             ▼                                           │
                    ┌─────────────────┐                                  │
                    │   Remediation   │ (conditional, only on WEAK/FAIL) │
                    │     Drafter     │                                  │
                    └────────┬────────┘                                  │
                             │  DefenderResponse (draft)                 │
                             ▼                                           │
                    ┌─────────────────┐                                  │
                    │   Compliance    │ NLI verification of every cited  │
                    │     Guard       │ claim. Blocks on hallucination.  │
                    └────────┬────────┘                                  │
                             │                                           │
   DefenderResponse  ◀───────┘                                           │
   (PASSED or BLOCKED)                                                   │
                                                                         │
   All decisions traced to Langfuse. Full replay supported. ─────────────┘
```

**Why synthesis and verification are separate agents.** This is the architectural decision that makes the system safe for compliance work. The agent that produces output is *not* the agent that verifies output. Every cited claim in the response goes through Natural Language Inference (NLI) entailment checking against its source. If a claim cannot be verified, the response is **blocked**, not shown. This pattern is non-negotiable in v1 and any future version.

See [`docs/architecture.md`](docs/architecture.md) for full agent specifications and state schemas.

---

## What's in the box

| Component | Description |
|-----------|-------------|
| `app/agents/` | Four LangGraph agents plus the compliance guard |
| `app/retrieval/` | Hybrid retrieval (dense + sparse + RRF + reranker) |
| `app/api/` | FastAPI service exposing `/analyze` |
| `data/synthetic/` | 100 synthetic podiatry encounters with ground-truth labels |
| `data/corpus/` | Reference corpus: CMS, AAPC, JARALL Knowledge Center articles |
| `eval/` | Eval harness, RAGAS scoring, retrieval recall, NLI adversarial set |
| `ui/` | React + Tailwind demo UI |
| `infra/` | Docker Compose for local dev (Qdrant, Postgres, Langfuse) |
| `.github/workflows/` | CI with PR-blocking quality gates |

---

## Eval results

All numbers below come from the eval harness in `eval/` and are reproduced on every CI run. **Numbers shown are from the most recent main-branch build.**

| Metric                                        | Threshold | Latest |
|-----------------------------------------------|-----------|--------|
| Retrieval recall@5                            | ≥ 0.85    | _TBD_ |
| Overall verdict accuracy (test split)         | ≥ 0.85    | _TBD_ |
| Per-criterion accuracy (averaged)             | ≥ 0.80    | _TBD_ |
| Compliance guard recall (adversarial set)     | 1.00      | _TBD_ |
| RAGAS faithfulness                            | ≥ 0.88    | _TBD_ |
| End-to-end latency, p95                       | < 30s     | _TBD_ |

Quality gates are **PR-blocking**. A regression below threshold fails CI and prevents merge. There is no advisory mode.

To reproduce locally:

```bash
make eval
```

---

## Quick start

**Prerequisites:** Docker, Docker Compose, Python 3.11+, Node 20+, an OpenAI API key.

```bash
# 1. Clone and configure
git clone https://github.com/arunveligatla/modifier-25-defender.git
cd modifier-25-defender
cp .env.example .env
# Edit .env to add OPENAI_API_KEY

# 2. Bring up infrastructure (Qdrant, Postgres, Langfuse)
docker compose up -d

# 3. Build the reference corpus and index
make corpus

# 4. Generate synthetic encounters (deterministic, seed=42)
make synthetic-data

# 5. Run the eval harness
make eval

# 6. Start the API and the demo UI
make dev
# API at http://localhost:8000
# UI at http://localhost:5173
```

Setup time on a clean machine: ~10 minutes including Docker pull and corpus indexing.

---

## Reproducibility

Every result in this README is reproducible from a clean clone. Specifically:

- **Synthetic data generation is deterministic** given a seed. The 100-encounter test corpus is fully regenerated from `make synthetic-data` with `seed=42`.
- **Reference corpus indexing is idempotent**. `make corpus` rebuilds Qdrant + BM25 from `data/corpus/` source documents.
- **LLM calls are cached** by content hash during eval (`eval/.cache/`). Re-running the eval harness against the same prompts and contexts hits the cache, not the API.
- **All eval thresholds are defined in `eval/thresholds.yaml`** and enforced in CI. Changing a threshold requires a PR, code review, and rationale in the PR description.

---

## Ethics and safety

Built-in guardrails, not afterthoughts:

- **No autonomous coding.** The system never assigns CPT, ICD-10, HCPCS, or modifier codes. It evaluates documentation supporting an existing code; it does not propose codes.
- **No autonomous editing.** The system never modifies the source note. Suggested remediation language appears in a separate UI panel marked as suggestions for clinician review.
- **No claim submission.** Out of scope at the architectural level. The system has no payer, clearinghouse, or EHR write integration and is not designed to acquire one.
- **Compliance guard is mandatory.** Every cited claim is NLI-verified before reaching the user. There is no bypass flag.
- **Human-in-the-loop.** Every output is intended for coder review. The UI is designed to make accept/modify/reject the obvious next action.
- **Citation-first synthesis.** No claim is shown without a source citation. Empty-evidence outputs are a hard failure, not a degraded mode.
- **Auditability.** Every agent decision is logged to Langfuse with the inputs, retrieved sources, agent state, and output. Full replay supported.

---

## Limitations

This v1 is a focused demo, not a production deployment.

- **Synthetic data only.** All encounters in this repo are programmatically generated. The system has not been validated on real PHI and is not HIPAA-compliant for real-PHI processing.
- **Modifier 25 only.** Adjacent modifiers (24, 57, 59, X{EPSU}) are out of scope.
- **Single-encounter analysis.** No longitudinal patient analysis. No provider-level utilization analytics (the Pre-Payment Review trigger).
- **No EHR integration.** Notes are pasted or uploaded as text. Direct integration with NextGen, eClinicalWorks, or ModMed is deferred to v2.
- **English only.** No multilingual support.
- **Reference corpus is intentionally narrow.** ~30-60 documents. Expansion is part of v1.1.
- **No multi-tenancy.** Single-user demo. Auth is out of scope for v1.

See [`docs/limitations.md`](docs/limitations.md) for the full list.

---

## Tech stack

- **Orchestration:** LangGraph (typed state, conditional routing, persistence to Postgres)
- **LLM:** OpenAI GPT-4o for synthesis, `text-embedding-3-large` for dense retrieval
- **Retrieval:** Qdrant (dense) + BM25 (sparse) + Reciprocal Rank Fusion + cross-encoder rerank (`BAAI/bge-reranker-v2-m3`)
- **Verification:** DeBERTa-v3-large-mnli for NLI entailment checking
- **API:** FastAPI + Pydantic v2
- **UI:** React 18 + Tailwind + Vite
- **Tracing:** Langfuse (self-hosted)
- **Eval:** RAGAS + custom JARALL Standard eval harness
- **CI:** GitHub Actions with PR-blocking quality gates

---

## Repository layout

```
modifier-25-defender/
├── app/
│   ├── agents/         # LangGraph agents
│   ├── retrieval/      # Hybrid retrieval and reranking
│   ├── api/            # FastAPI service
│   └── schemas/        # Pydantic data contracts
├── data/
│   ├── synthetic/      # Generated encounter notes + ground truth
│   └── corpus/         # Reference documents (CMS, AAPC, JARALL)
├── eval/
│   ├── retrieval/      # Recall@5 eval set
│   ├── defensibility/  # End-to-end accuracy harness
│   ├── adversarial/    # Hallucination test set for compliance guard
│   └── thresholds.yaml # PR-blocking thresholds
├── ui/                 # React demo
├── infra/
│   └── docker-compose.yaml
├── docs/
│   ├── architecture.md
│   ├── limitations.md
│   └── eval-methodology.md
├── prompts/            # Agent prompts (versioned)
├── .github/workflows/  # CI
├── Makefile
└── README.md
```

---

## Documentation

| Document | Audience | Purpose |
|----------|----------|---------|
| [`docs/architecture.md`](docs/architecture.md) | Engineers | Full agent specs, state schemas, retrieval design |
| [`docs/eval-methodology.md`](docs/eval-methodology.md) | Engineers, reviewers | How accuracy is measured and what the thresholds mean |
| [`docs/limitations.md`](docs/limitations.md) | Everyone | Honest list of what v1 does and does not do |
| [`docs/synthetic-data.md`](docs/synthetic-data.md) | Engineers, clinicians | How encounters are generated, parameter space, ground-truth labeling |
| [`specs/001-modifier-25-defender/spec.md`](specs/001-modifier-25-defender/spec.md) | Engineers | The full v1 technical specification this implementation follows (translated into spec-kit format) |
| [`specs/001-modifier-25-defender/plan.md`](specs/001-modifier-25-defender/plan.md) | Engineers | Implementation plan with Constitution Check |
| [`specs/001-modifier-25-defender/tasks.md`](specs/001-modifier-25-defender/tasks.md) | Engineers | 106-task implementation breakdown grouped by user story |
| [`.specify/memory/constitution.md`](.specify/memory/constitution.md) | Everyone | Binding project principles (v1.0.0); supersedes ad-hoc practice |
| [`docs/SPEC_DRIVEN_DEVELOPMENT.md`](docs/SPEC_DRIVEN_DEVELOPMENT.md) | Contributors | Spec-Driven Development workflow guide for this repo |

---

## Roadmap

**v1 (current):** Single-encounter analysis with the four JARALL Standard criteria, synthetic data only, no EHR integration.

**v1.1 (next):** Reference corpus expansion. Provider-level utilization analytics (the >50% Pre-Payment Review trigger). Improved synthetic data variety.

**v2 (future):** Adjacent modifier support (24, 57, 59). Direct EHR integration via Bulk FHIR + EHI Export + HL7 v2 financial messages. Multi-tenant deployment. BAA-backed real-PHI processing.

Each milestone has its own spec document under [`specs/`](specs/). The v1 spec is at [`specs/001-modifier-25-defender/spec.md`](specs/001-modifier-25-defender/spec.md).

---

## Contributing

This is a solo project for now. Issues and discussion are welcome. PR contributions accepted with a CLA after v1 ships.

---

## Author

**Arun Veligatla**, Senior Software Engineer, healthcare SaaS and applied AI for regulated workflows.

11+ years building production EHR, e-prescribing, and revenue cycle systems for podiatry practices, including TRAKnet (the leading podiatry EHR) at Nemo Health and ModMed EMA migration work. Built PolicyMind at ModMed: a four-agent RAG platform on Azure AI Foundry with citation accuracy of 92.5% and CI-enforced quality gates. This project applies the same architecture pattern to a problem JARALL Medical Management has publicly identified as costly and growing.

[arun.veligatla@gmail.com](mailto:arun.veligatla@gmail.com) · [LinkedIn](https://linkedin.com/in/arun-v-311419137) · [GitHub](https://github.com/arunveligatla)

---

## License

MIT. See [LICENSE](LICENSE).

---

## Acknowledgments

- The four-criterion defensibility framework is operationalized from Dr. Alan Bass's [Modifier 25 Mastery](https://www.jarallmedical.com/blog/modifier-25-mastery) article (April 23, 2026), used with attribution.
- CMS National Correct Coding Initiative (NCCI) Policy Manual chapters on E/M services.
- AAPC publicly available coding guidance.
- The PolicyMind architecture pattern (Anthropic-style synthesis + verification separation) developed during my time at Modernizing Medicine.
