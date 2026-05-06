# Limitations

Honest list of what v1 does and does not do. Source: spec
`specs/001-modifier-25-defender/spec.md` Out of Scope and Open Questions.

## Out of scope for v1

- **Real PHI ingestion**. Constitution Principle IV. v1 accepts
  synthetic data only. The PHI denylist gate runs on every PR; the
  /analyze route refuses requests whose `note_text` contains real-PHI
  markers.
- **Direct EHR integration**. NextGen, eClinicalWorks, ModMed write
  paths are out of scope. See `JARALL_EHR_Integration_Brief.docx` in
  the parent directory for the v2 deferred backlog.
- **Auto-applying remediation**. AC-006-3 + Constitution Principle III.
  The drafter produces parallel `RemediationSuggestion` items; the UI
  renders them in a separate panel.
- **Claim submission, denial appeal, payer-facing actions**. The
  product is an advisor, not an actor.
- **Multi-encounter / longitudinal analysis**. Provider-level Modifier
  25 utilization analytics (the >50 percent Pre-Payment Review trigger)
  is v1.1.
- **Adjacent modifiers (24, 57, 59, X{EPSU})**. v1 covers Modifier 25
  only.
- **Multi-tenant deployment**. Single-user demo. No auth in v1.
- **Production observability beyond Langfuse self-hosted**. No
  cloud-native logging or metrics stack.

## Deferred to v1.1

- Real corpus expansion (replace placeholder documents under
  `data/corpus/` with real CMS NCCI Policy Manual chapters, MLN Matters
  articles, AAPC public articles, JARALL Knowledge Center posts, and
  2026 Medicare Claims Processing Manual chapters).
- DEGRADED compliance state (Q2 deferred). v1 is two-state PASSED or
  BLOCKED.
- LangGraph Postgres checkpoint persistence. v1 ships with the
  synchronous orchestrator and trace_id replay.
- Real Hugging Face NLI weights wired into CI. v1 unit tests use
  `NLIStub`; the production path lazy-loads `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`.
- Provider-level utilization analytics.
- Coder feedback loop (thumbs up/down on remediations).
- Batch CSV upload mode.

## Known v1 caveats

- The placeholder corpus is 6 short summary documents, not the 30 to 60
  documents that AC-002-1 requires. The retrieval framework, RRF
  fusion, and rerank are fully testable on the placeholder; replacing
  the documents is a content-only follow-up under T109.
- The parser ground-truth offsets used for AC-003-2 are not yet
  produced by the synthetic generator. The harness is implemented and
  has unit tests; the eval set lives at `data/parser_eval/dev.jsonl`
  and is created when ground-truth offsets land.
- The drafter clinical-reasonableness metric (AC-006-4) is a manual
  review by a CPC-trained reviewer, not an automated harness. The
  manual-review notes land at `docs/remediation-review-week3.md`.
- The eval orchestrator's `empty_report()` skeleton causes the gate
  checker to fail every category until real per-harness wiring lands.
  This is intentional: the harness must not silently pass when nothing
  has been evaluated.
- Cross-browser sanity (AC-008-5) requires a manual pass; spec-kit
  cannot exercise a real browser. Run the UI against the demo dataset
  in Chrome and Safari current versions before recording the demo.
- The UI does not include a `/quality` route in v1 (deferred to T407
  follow-up). The latest eval report is available as a workflow
  artifact from the nightly job.

## Constitutional commitments that limit the design space

- **Citation-First Synthesis** (Principle I). Every model output cites
  source spans. Empty-evidence outputs are a hard failure, not a
  degraded mode.
- **Synthesis and Verification Are Separate** (Principle II,
  NON-NEGOTIABLE). The Compliance Guard runs on every response. There
  is no bypass flag. The import-graph lint enforces this at the code
  level.
- **No Autonomous Coding Action** (Principle III). The system never
  assigns codes, edits the source note, or submits claims.
- **Synthetic Data Only (v1)** (Principle IV). Real PHI is never
  permitted in any commit, ever, including deleted commits. v2 may
  introduce real PHI behind a Business Associate Agreement.
- **Full Auditability and Replay** (Principle V). Every response
  carries a `trace_id` and the LangGraph state is persistable to
  Postgres for replay (deferred to v1.1 in this implementation).
