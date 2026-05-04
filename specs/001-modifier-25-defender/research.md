# Phase 0 Research: Modifier 25 Defender (v1 MVP)

**Feature**: `001-modifier-25-defender`
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Date**: 2026-05-03

This document consolidates the design decisions referenced by the plan. Most decisions are inherited from the v1 design source (`../../Modifier25_Defender_Spec.docx`) and the Q1..Q5 clarification round; this file records them in the spec-kit Decision/Rationale/Alternatives format for traceability and to satisfy `/speckit-plan` Phase 0 expectations. There are no remaining `NEEDS CLARIFICATION` markers.

## R1. LLM provider for synthesis agents

- **Decision**: OpenAI GPT-4o for synthesis (Documentation Parser, Defensibility Analyzer, Remediation Drafter). `text-embedding-3-large` for dense retrieval embeddings.
- **Rationale**: GPT-4o has strong instruction following for structured-output tasks (`response_format=json_schema`), reasonable per-call cost ($0.05 to $0.10 per encounter for the analyzer's 4 calls), and parity with the original PolicyMind reference architecture cited in the project README. `text-embedding-3-large` produces 3072-dim embeddings with documented retrieval quality strong enough to clear AC-002-3 with hybrid search.
- **Alternatives considered**:
  - Claude Sonnet 4.7 / Opus: comparable quality, but switching providers introduces an extra integration vector and the eval cache key (Q5) would need provider in the hash. Deferred to v1.1 if cost or latency tuning makes it attractive.
  - Local open-weight models (Llama 3.1 70B, Qwen 2.5 72B): cost-attractive but require GPU infra in the demo environment; v1 ships local-only via Docker Compose without GPU assumptions.

## R2. Retrieval architecture

- **Decision**: Hybrid retrieval. Dense (Qdrant + `text-embedding-3-large`) plus sparse (BM25 over identical chunk set). Fuse with Reciprocal Rank Fusion (RRF, k=60). Rerank top-20 fused candidates with `BAAI/bge-reranker-v2-m3` cross-encoder to top-5 reranked context.
- **Rationale**: Dense alone misses keyword-heavy CMS chapter references; sparse alone misses semantic paraphrases of CMS guidance. RRF is parameter-free fusion and resilient to score scale differences between retrievers. Cross-encoder rerank adds the precision needed to clear AC-002-3 (recall@5 >= 0.85).
- **Alternatives considered**:
  - ColBERT-style late interaction: stronger than cross-encoder rerank in some benchmarks, but ColBERT-v2 inference infra is heavier and not justified for a 30 to 60 document corpus.
  - LLM-based reranker (GPT-4o-mini judging top-20): viable but adds API latency and cost; cross-encoder is local CPU and clears AC-002-5 (p95 < 800ms).

## R3. Compliance Guard implementation

- **Decision**: NLI verification via DeBERTa-v3-large-mnli (or equivalent open-weight NLI head). Local CPU inference (`transformers`). Threshold: claim verified if entailment probability >= 0.75. Per Q2 resolution: any flagged claim demotes the response to BLOCKED in v1; DEGRADED is deferred to v1.1.
- **Rationale**: Constitution Principle II requires the Compliance Guard to be architecturally separate from synthesis. A separate model (NLI head, not GPT) plus local inference (no shared API path) makes the separation operational, not just code-organizational. DeBERTa-v3-large-mnli is well-studied for entailment, runs in <500ms on CPU at the batch sizes here (8 to 12 citations per response), and clears AC-005-5 (p95 < 3s).
- **Alternatives considered**:
  - GPT-4o-as-judge with structured prompt: more flexible, but verifier sharing the synthesis-side model family undermines the architectural-separation argument and makes the same-class-failure-modes risk concrete.
  - Custom fine-tuned entailment model: out of scope for v1; would require labeled medical-coding entailment data we do not have.
  - Threshold tuning: held to 0.75 for v1. R4 mitigation (tune on a held-out 30 verified-correct claims if false-positive rate exceeds 10% per AC-005-3).

## R4. Synthetic encounter generator

- **Decision**: Templated generator over a 12-dimension parameter space, deterministic with seed = 42 (Q4 resolution). Stratified sampling to produce 100 encounters with at least 25 PASS and 25 FAIL on overall verdict, covering at least 6 distinct procedure codes. Manual review of the first 20 encounters to catch generator drift.
- **Rationale**: Real PHI is forbidden by Constitution Principle IV; templated generation gives reproducibility and labeled ground truth. 12 dimensions are enough to produce meaningful variation while remaining tractable to label. seed=42 because the project README and the v1 spec both reference reproducibility from `seed=42`.
- **Alternatives considered**:
  - GPT-4 free-form generation: produces homogeneous slop and unreliable ground-truth labels; rejected per the v1 design source.
  - Public synthetic-EHR datasets (Synthea, MIMIC-IV de-identified): real-world signal but neither covers podiatry encounter notes at the level of detail needed; reserved for v1.1 augmentation.

## R5. Reference corpus composition

- **Decision**: 30 to 60 documents drawn from CMS NCCI Policy Manual chapters on E/M services, MLN Matters articles related to Modifier 25, AAPC publicly available coding articles on Modifier 25, JARALL Knowledge Center Modifier 25 posts, and 2026 Medicare Claims Processing Manual chapters. Chunked at 200 to 400 tokens with 50-token overlap. Each chunk indexed with metadata: source document, section heading, publication date, authority tier (CMS > AAPC > JARALL > other).
- **Rationale**: CMS material is dense and authoritative; AAPC and JARALL provide operationalized guidance and the four-criterion framework. Authority tier matters when retrieved chunks contradict.
- **Alternatives considered**:
  - Wider corpus (200+ documents): unnecessary for v1 scope and makes recall@5 evaluation harder to keep stable. Corpus expansion is v1.1.
  - Paywalled AAPC content: legally questionable to ingest; v1 uses only freely accessible AAPC pages.

## R6. Orchestration framework

- **Decision**: LangGraph with typed state (TypedDict / Pydantic v2 model) and PostgreSQL checkpointing for replay support.
- **Rationale**: Constitution Principle V requires full audit and replay. LangGraph's checkpoint persistence + Langfuse trace integration gives that out of the box. Typed state catches schema drift between agents at startup, not at runtime.
- **Alternatives considered**:
  - Plain function composition: simpler, but loses checkpoint-based replay and the conditional-routing primitive for the Drafter (only runs on WEAK or FAIL).
  - LangChain LCEL: lower-level, requires hand-rolling persistence; LangGraph subsumes the relevant pieces.

## R7. Eval cache key composition (Q5)

- **Decision**: Cache key = SHA-256(prompt_text + retrieval_context_json + model_version + temperature + provider_tag).
- **Rationale**: Q5 option B. Including model version and temperature forces full re-evaluation on a model upgrade or temperature change, preventing silent eval drift. The provider_tag is included for forward compatibility with R1's deferred multi-provider option; in v1 it is a fixed string `openai`.
- **Alternatives considered**:
  - Q5 option A (prompt + context only): cheaper but masks eval drift across model bumps. Rejected.
  - Q5 option C (include provider only): partial fix; rejected in favor of B.

## R8. UI architecture

- **Decision**: React 18 + Tailwind + Vite, single-page app, no auth, no state-management library beyond React's built-ins. Two-state response rendering (PASSED, BLOCKED) per Q2.
- **Rationale**: Demo scope. Vite gives fast HMR. No auth keeps the demo clean. Two-state rendering keeps the trust story unambiguous; DEGRADED is deferred.
- **Alternatives considered**:
  - Next.js: SSR not needed for a single-user local demo; rejected.
  - Streamlit: faster to build but harder to make screenshot-ready (AC-008-4) and harder to express the click-citation-to-highlight interaction (AC-008-2).

## R9. CI implementation

- **Decision**: GitHub Actions with separate workflows for PR (`ci.yml`) and nightly (`nightly-eval.yml`). PR workflow runs lint (ruff), format (black --check), type (mypy), unit tests (pytest), em-dash gate (Q1: option C scoped paths), and the eval harness with content-hash cache. Nightly workflow re-runs the full eval against `main` without the cache and posts a delta report.
- **Rationale**: PR workflow needs to be fast (cache hits keep it under 10 minutes for unchanged prompts/retrieval). Nightly catches drift the cache might mask.
- **Alternatives considered**:
  - Run full eval without cache on every PR: clears any drift risk but explodes API cost (R3).
  - Skip eval on PRs and run only nightly: removes the PR-blocking gate, violates AC-007-6 and Constitution Principle II.

## R10. Em-dash CI gate scope (Q1)

- **Decision**: Em-dash (U+2014) check runs on changed files matching `app/**`, `eval/**`, `ui/src/**`, `docs/**`, `specs/**`, `*.md`, `prompts/**`, and any plain-text fixture under `tests/**`. Skipped: `data/synthetic/encounters/**` (LLM-generated fixtures), `eval/.cache/**` (gitignored anyway), and any file path containing `runtime-output` or matching `*.generated.*`.
- **Rationale**: Q1 option C distinguishes curated text (governed by the constitution) from LLM-generated content (nudged by prompt instruction). LLM remediation suggestions and generated synthetic encounters are not curated text.
- **Alternatives considered**:
  - Q1 option A (all paths): would force post-processing on remediation output; conflicts with citation fidelity (rephrasing a quoted policy span to avoid an em-dash could break the citation match).
  - Q1 option B (UI strings exempt): rejected; UI strings are curated and should be on-policy.
