# Architecture

This document describes the v1 implementation architecture of Modifier 25
Defender. Spec source: `specs/001-modifier-25-defender/spec.md`. Constitution
source: `.specify/memory/constitution.md`.

## Pipeline overview

```
DefenderRequest
      |
      v
+---------------+
|   /analyze    |  POST route in app/api/routes.py
+---------------+
      |
      v
+---------------+
| Orchestrator  |  app/agents/orchestrator/graph.py (synchronous v1)
+---------------+
      |
      |  Documentation Parser (EPIC-003)
      v
+---------------+
|    Parser     |  app/agents/parser/agent.py
+---------------+
      |  ParsedEncounter
      v
+---------------+      retrieval payload from
|   Analyzer    |---->  app/retrieval/* (EPIC-002)
+---------------+      <- BM25 + Qdrant + RRF + cross-encoder rerank
      |  DefensibilityAssessment
      v
+---------------+
|  (optional)   |  Drafter only when overall in {WEAK, FAIL}
|    Drafter    |  app/agents/drafter/agent.py
+---------------+
      |
      v
+---------------+
|   Compliance  |  app/agents/compliance_guard/agent.py (EPIC-005)
|     Guard     |  ARCHITECTURALLY SEPARATE FROM SYNTHESIS
+---------------+
      |  PASSED or BLOCKED
      v
DefenderResponse
```

## Module map

| Module                              | Role                                                        |
|-------------------------------------|-------------------------------------------------------------|
| `app/api/main.py`                   | FastAPI app factory; mounts the analyze router and healthz. |
| `app/api/routes.py`                 | POST /analyze; PHI denylist + procedure code allowlist.     |
| `app/agents/parser/`                | Documentation Parser. JSON-schema enforced. One retry.       |
| `app/agents/analyzer/`              | Defensibility Analyzer. Four per-criterion calls + same-site special case. |
| `app/agents/drafter/`               | Remediation Drafter. Conditional on WEAK or FAIL overall.    |
| `app/agents/compliance_guard/`      | Verifier side. NLI entailment over every Citation.          |
| `app/agents/orchestrator/`          | Wiring layer. Neutral side of the import-graph lint.        |
| `app/retrieval/`                    | Hybrid retrieval (BM25 + Qdrant + RRF + reranker).          |
| `app/llm/`                          | OpenAI client wrapper with content-hash cache (R7 / Q5).    |
| `app/observability/`                | Langfuse client + null fallback.                            |
| `app/schemas/`                      | Pydantic v2 data contracts.                                 |
| `eval/`                             | Harnesses + thresholds + orchestrator + report writer.       |
| `data/synthetic/`                   | 100 generated encounters, deterministic at seed=42.         |
| `data/corpus/`                      | Reference corpus (placeholder; replace via T109 follow-up). |
| `data/adversarial/`                 | 20 hallucinated claims for Compliance Guard recall (AC-005-2). |
| `data/retrieval_eval/`              | 10 retrieval questions paired with expected sources.        |
| `prompts/`                          | Versioned prompt files (parser/v1, analyzer/*/v1, drafter/v1). |
| `scripts/check_emdash.py`           | CS-3 em-dash gate.                                          |
| `scripts/check_phi.py`              | Constitution Principle IV PHI denylist gate.                |
| `scripts/check_imports.py`          | Constitution Principle II import-graph lint (T138).         |
| `ui/`                               | React 18 + Tailwind + Vite demo UI.                         |
| `infra/`                            | Docker Compose (Qdrant, Postgres, Langfuse, backend, UI).   |

## State model

Pydantic v2 models in `app/schemas/`. Every cross-module boundary uses a
typed model rather than `dict[str, Any]`. The contract surface is:

- `DefenderRequest` (input to /analyze)
- `ParsedEncounter` (parser output)
- `CriterionScore` and `DefensibilityAssessment` (analyzer output)
- `RemediationSuggestion` (drafter output)
- `Citation` and `TextSpan` (shared primitives)
- `CorpusChunk` (retrieval indexed unit)
- `DefenderResponse` (output of /analyze)

Two-state `compliance_status` per Q2 resolution (DEGRADED deferred to v1.1).

## Compliance Guard separation (Constitution Principle II)

Three independent layers of enforcement:

1. **Module placement**. `app/agents/compliance_guard/` does not import
   from any synthesis-side agent (`parser`, `analyzer`, `drafter`).
2. **Type system**. The Guard depends only on `NLIVerifier` and the
   shared schemas. It does not see the synthesis `_LLMClientLike`.
3. **CI**. `scripts/check_imports.py` (T138) walks the AST of every
   `app/agents/**/*.py` file and emits violations on any import that
   crosses the boundary. The check runs on every PR.

The orchestrator at `app/agents/orchestrator/` is the only "neutral"
package allowed to import both sides. The import-graph lint excludes it
by design; it is the wiring layer.

## Data flow under BLOCKED

When the Compliance Guard fails entailment for any Citation, the
orchestrator returns a `DefenderResponse` with `compliance_status =
"BLOCKED"`, `assessment = None`, `remediations = []`, and a populated
`blocked_reasons` list. The `parsed` field is preserved so the coder can
see how their note was interpreted; everything downstream of synthesis
is stripped to avoid leaking unverified content.

## Cache invariants

`app/llm/openai_client.py` keys cache entries on prompt + retrieval
context + model + temperature + provider tag. A model upgrade or
temperature change forces full re-evaluation. Reference: research.md R7,
spec OQ-T5 (Q5 option B).

## Observability

`app/observability/langfuse_client.py` returns either a real Langfuse
adapter or a `NullLangfuseClient` when credentials are missing. The
orchestrator wraps each request in `trace_session` and logs spans for
parser, analyzer, drafter (when invoked), and compliance_guard. Every
`DefenderResponse` carries the trace_id (Constitution Principle V).

## Where the architecture defers to v1.1

- Real corpus ingestion (T109 follow-up) populates `data/corpus/` with
  CMS, AAPC, JARALL, and CPM source documents. The retrieval framework
  is fully testable on the placeholder corpus shipped here.
- DEGRADED compliance state (Q2 future option). v1 is two-state.
- LangGraph checkpoint persistence to Postgres. The synchronous
  orchestrator does not need it; trace_id replay is sufficient for v1.
- Real Hugging Face NLI weights. Tests use `NLIStub` and the production
  path lazy-loads `microsoft/deberta-v3-large-mnli`.
