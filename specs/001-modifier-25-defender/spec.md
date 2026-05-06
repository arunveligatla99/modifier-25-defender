# Feature Specification: Modifier 25 Defender (v1 MVP)

**Feature Branch**: `feature/001-modifier-25-defender`
**Created**: 2026-05-03
**Status**: Draft (translated from v1 design source, awaiting user approval)
**Input**: User description: "Translate the Modifier 25 Defender v1 design specification (Modifier25_Defender_Spec.docx in the parent directory) into a spec-kit feature spec preserving EPIC structure, AC-XXX-N acceptance criteria, data contracts, eval methodology, and risk register."

## Translation Note

This specification is a translation of a pre-existing v1 design document (`../Modifier25_Defender_Spec.docx`) into the spec-kit format. The source document is the authoritative design intent. Acceptance criteria, threshold numbers, data contracts, EPIC structure, and risk register have been preserved verbatim. This spec is intentionally more technical than the typical spec-kit "WHAT-not-HOW" output: the v1 design intent already commits to a specific architecture (synthesis plus separate verification, hybrid retrieval, NLI compliance guard) and that architecture is part of the feature definition, not an implementation detail. Tech-stack commitments live in `.specify/memory/constitution.md`; threshold values are reproduced here for traceability and live authoritatively in `eval/thresholds.yaml` once that file lands.

Document conventions for this spec match the source:

- MUST, SHOULD, MAY follow RFC 2119 semantics. MUST is non-negotiable for v1; SHOULD is strongly preferred but can slip; MAY is opportunistic.
- Acceptance criteria are prefixed with `AC-{EPIC}-{N}` and are pass/fail, not subjective.
- Out-of-scope items are listed explicitly per EPIC and at the top level. If it is not in scope and not in the deferred backlog, it does not exist for v1.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coder reviews a Modifier 25 encounter for defensibility (Priority: P1)

A medical coder at a podiatry practice has an encounter coded `99213 + 11721 + Modifier 25` flagged for review. The coder pastes the encounter note into the tool along with the E/M code, the procedure code, and the Modifier 25 attachment. Within roughly 20 seconds, the tool returns a structured defensibility assessment scored against the four JARALL Standard criteria, with each verdict grounded in cited evidence from the source note and from external policy (CMS, AAPC, JARALL). The coder uses the assessment to decide whether to push back to the clinician for documentation strengthening or to let the claim go through as-is.

**Why this priority**: This is the entire reason the product exists. Without this story, no other story has value.

**Independent Test**: A reviewer can paste a synthetic encounter note from `data/synthetic/` into the demo UI, click Analyze, and within 30 seconds see a per-criterion verdict with at least one citation per criterion. If the verdict matches the ground-truth label for that synthetic encounter on at least 85% of test-split encounters, the story is validated.

**Acceptance Scenarios**:

1. **Given** a synthetic encounter labeled FAIL on overall verdict, **When** the coder submits it, **Then** the tool returns an overall FAIL verdict with at least one citation per criterion explaining why each weak criterion failed, and the response is marked PASSED by the Compliance Guard.
2. **Given** a synthetic encounter labeled PASS on overall verdict, **When** the coder submits it, **Then** the tool returns an overall PASS verdict with citations to the source note spans that establish each criterion.
3. **Given** an encounter the analyzer cannot ground a critical claim for, **When** the response would otherwise expose an unsupported FAIL claim to the user, **Then** the Compliance Guard blocks the response, the user sees a BLOCKED state with structured `blocked_reasons`, and no synthesis output is shown.
4. **Given** the coder clicks a citation in the assessment, **When** the citation references a span in the source note, **Then** the corresponding span is highlighted in the source-note panel.

### User Story 2 - Coder receives drafted remediation language for weak or failing criteria (Priority: P2)

When the assessment from Story 1 returns WEAK or FAIL on at least one criterion, the coder also sees targeted documentation language they could ask the clinician to add. Each suggestion is tied to a specific weak criterion and cites the policy that motivates it. The coder reviews each suggestion, accepts/modifies/rejects in their workflow (out of system in v1), and never has the source note auto-modified.

**Why this priority**: Suggestions multiply the tool's value (turns a verdict into an actionable next step), but the verdict itself in Story 1 is the load-bearing capability.

**Independent Test**: For 20 synthetic encounters labeled WEAK or FAIL, the tool produces at least one remediation suggestion per weak criterion, each with at least one policy citation, and a CPC-trained reviewer (or careful self-review against the source policies, in the absence of one) finds the suggestion clinically reasonable on at least 80% of cases.

**Acceptance Scenarios**:

1. **Given** an encounter scored WEAK on Independent MDM, **When** remediation runs, **Then** the response contains at least one `RemediationSuggestion` whose `criterion` is `independent_mdm`, with a non-empty `suggested_addition` and at least one policy citation in `motivation`.
2. **Given** an encounter scored PASS overall, **When** the analyzer completes, **Then** the Remediation Drafter is not invoked and the response contains an empty `remediations` list.
3. **Given** a remediation suggestion is shown, **When** the user views it, **Then** it appears in a UI panel visually distinct from the source note, marked clearly as a suggestion for clinician review, and the source note panel is not modified.

### User Story 3 - Eval engineer enforces accuracy and safety in CI on every PR (Priority: P3)

An engineer opens a PR that touches retrieval, an agent, or a prompt. CI runs the eval harness against the test split and the adversarial set, and fails the PR if any quality gate regresses below threshold. There is no advisory mode; a regression on the Compliance Guard's adversarial recall blocks merge regardless of which file changed.

**Why this priority**: Without this story, the production-grade claim is empty: any regression on accuracy or hallucination guard could ship silently. With this story, accuracy and safety are PR-blocking by construction. Lower priority than Stories 1 and 2 only because it does not directly produce the user-facing assessment, but it gates the whole project's claim to defensibility.

**Independent Test**: Open a PR that intentionally weakens the Compliance Guard threshold (or removes a guard call) and verify CI fails with a clear error pointing at the failing gate. Open a PR that improves retrieval and verify CI passes with the new (higher) recall.

**Acceptance Scenarios**:

1. **Given** a PR that drops retrieval recall@5 below 0.85, **When** CI runs, **Then** the PR is blocked from merge with an explicit gate-failure message.
2. **Given** a PR that drops Compliance Guard adversarial-set recall below 1.00, **When** CI runs, **Then** the PR is blocked with an explicit Compliance Guard regression message.
3. **Given** a PR that proposes to lower a threshold in `eval/thresholds.yaml`, **When** CI runs, **Then** the threshold change itself is visible in the diff, the PR description must include rationale, and reviewer approval is required to merge (CI alone is not sufficient).

### Edge Cases

- **Ambiguous note segments**: when the Documentation Parser cannot confidently classify a paragraph as HPI vs procedure note, the segment MUST be surfaced in `ambiguous_segments` rather than silently coerced into one field.
- **Empty evidence**: a `CriterionScore` with an empty `evidence` list is a hard failure, not a degraded mode. The Compliance Guard MUST reject any response that contains a `CriterionScore` with no citations.
- **Same-site E/M and procedure**: when the E/M and procedure are on the same anatomical site, Site-Specificity is N/A rather than PASS/WEAK/FAIL, and the verdict is computed across the remaining three criteria.
- **Schema-invalid agent output**: if the Documentation Parser returns JSON that does not validate against the `ParsedEncounter` schema, retry once with the validation error fed back; on a second failure surface a structured error to the Orchestrator.
- **Cost runaway in eval**: re-running the eval harness against the same prompts and contexts MUST hit a content-hash cache (`eval/.cache/`) rather than the LLM API. Cache key MUST include prompt text, retrieval context, model version, and temperature so a model upgrade or temperature change forces re-evaluation rather than masking eval drift behind a stale cache hit (resolved Q5: option B).
- **Adversarial note**: a note crafted to look like a valid note but with internally contradictory content MUST not break the parser; it should be parsed best-effort with `ambiguous_segments` populated, and the analyzer's verdict should reflect the contradictions in its evidence.
- **Highly verbose notes**: notes longer than the typical 200-400 token reference-corpus chunk size MUST still be parsed correctly; the `ParsedEncounter` field offsets MUST cover their original spans.

## Requirements *(mandatory)*

### Functional Requirements

Functional requirements are organized by EPIC, mirroring the EPIC structure of the v1 design source. Each EPIC's acceptance criteria are preserved verbatim with their original `AC-{EPIC}-{N}` identifiers and threshold numbers. Dependency order: EPIC-001 -> EPIC-002 -> (EPIC-003 || EPIC-004) -> EPIC-005 -> EPIC-006 -> (EPIC-007 || EPIC-008).

#### EPIC-001: Synthetic Encounter Generation

**Why this EPIC is first**: every other EPIC needs encounter data. Real PHI is off the table (Constitution Principle IV). This EPIC builds a structured generator producing realistic, varied, and labeled encounters on demand.

**Approach**: 12-dimension parameter space (presenting condition, comorbidities, procedure type, site, E/M level, separable problem, site-specificity stated, MDM separability, exam separability, narrative style, ground-truth defensibility label). Stratified sampling. Templated generation, not free-form. Manual review of first 20 to catch generator drift.

**Acceptance criteria**:

- **AC-001-1**: System MUST produce 100 synthetic encounters across the defined parameter space.
- **AC-001-2**: System MUST include ground-truth labels for each criterion (`distinct_cc`, `separate_exam`, `independent_mdm`, `site_specificity`) and overall verdict.
- **AC-001-3**: System MUST include at least 25 encounters labeled FAIL on overall verdict (sufficient negative examples for eval).
- **AC-001-4**: System MUST include at least 25 encounters labeled PASS on overall verdict.
- **AC-001-5**: System MUST cover at least 6 distinct procedure codes.
- **AC-001-6**: Generator code MUST be deterministic given a seed (reproducibility).
- **AC-001-7**: 20-encounter manual review MUST find <10% obvious unrealism (e.g., contradictory exam findings, anatomically impossible procedures).
- **AC-001-8**: Encounters MUST be split 70/15/15 into train/dev/test sets, fixed across runs.

**Out of scope for EPIC-001**: multi-encounter trajectories (longitudinal patient histories); procedures other than the listed podiatry codes; non-English notes.

#### EPIC-002: Reference Corpus and Retrieval

**Corpus contents**: CMS Modifier 25 guidance (NCCI Policy Manual chapters on E/M services, MLN Matters articles), AAPC publicly available coding articles on Modifier 25, JARALL Knowledge Center posts (Modifier 25 Mastery, 2026 E/M Shift, Medicare Fee Schedule Update, and other M25-relevant posts), relevant chapters of the 2026 Medicare Claims Processing Manual. Target corpus size for v1: 30 to 60 documents, chunked to roughly 200 to 400 tokens per chunk with 50-token overlap.

**Retrieval design**: hybrid retrieval (dense + sparse) with Reciprocal Rank Fusion (k=60), cross-encoder reranking. Each chunk indexed with metadata: source document, section heading, publication date, source authority tier (CMS > AAPC > JARALL > other).

**Acceptance criteria**:

- **AC-002-1**: System MUST ingest >=30 source documents into the chunked corpus.
- **AC-002-2**: System MUST persist a vector store with embeddings AND a BM25 index over the identical chunk set.
- **AC-002-3**: Hybrid retrieval (dense + sparse + RRF + rerank) MUST achieve recall@5 >=0.85 on a hand-curated 30-question retrieval eval set.
- **AC-002-4**: Each retrieved chunk MUST carry source metadata: document title, source URL or filename, publication date, authority tier.
- **AC-002-5**: Retrieval latency MUST be p95 <800ms on a single-node Qdrant Docker setup.
- **AC-002-6**: Re-indexing the corpus MUST be a single command (idempotent script).

**Eval methodology for retrieval**: 30 hand-curated questions paired with the chunk(s) that should be retrieved. Compute recall@5: of the 30 questions, how often does the relevant chunk appear in the top 5 returned? This eval set is run in CI on every PR that touches the corpus or retrieval.

#### EPIC-003: Documentation Parser Agent

**Approach**: single GPT-4o call with structured outputs (JSON schema enforced). Prompt includes 3 worked examples (one PASS, one WEAK, one FAIL encounter). Output validated against the `ParsedEncounter` schema. Validation failure triggers a single retry with the validation error fed back; second failure is a hard failure surfaced as an error to Orchestrator. Ambiguous segments MUST be surfaced explicitly rather than silently coerced.

**Acceptance criteria**:

- **AC-003-1**: System MUST extract CC, HPI, exam findings, MDM, and procedure note as distinct fields with character offsets.
- **AC-003-2**: System MUST achieve >=90% field-level accuracy on the dev split (15 encounters): a field is "correct" if its character offsets cover >=80% of the ground-truth span and <=120% of the ground-truth span.
- **AC-003-3**: System MUST surface `ambiguous_segments` rather than silently misclassifying. Manual review of dev split MUST find no silent misclassifications (segments classified into the wrong field without being flagged).
- **AC-003-4**: System MUST validate output against the `ParsedEncounter` schema. Schema-invalid output MUST trigger one retry.
- **AC-003-5**: Per-encounter latency MUST be p95 <5 seconds.

**Out of scope**: speech-to-text or scanned document parsing (text input only); multilingual support; structured EHR field extraction.

#### EPIC-004: Defensibility Analyzer Agent

**Four criteria operationalized (JARALL Standard)**:

- **Criterion 1: Distinct Chief Complaint**. PASS: CC names a problem distinct from the procedure's primary indication. WEAK: CC names a problem related to but not identical to the procedure's primary indication. FAIL: CC is solely the indication for the procedure.
- **Criterion 2: Separate Exam Findings**. PASS: exam documents findings on a body part or condition not addressed by the procedure. WEAK: general findings with some non-procedure-related elements. FAIL: exam findings are solely the assessment of the procedure site.
- **Criterion 3: Independent Medical Decision Making**. PASS: MDM addresses a problem with risks, data, and management options independent of the procedure decision. WEAK: MDM mentions other problems but the dominant decision is the procedure. FAIL: MDM is solely the workup justifying the procedure.
- **Criterion 4: Site-Specificity**. PASS: when E/M and procedure are on different sites, both LT/RT (or T1-T9) modifiers are documented and present in the claim. WEAK: different sites implied but not modifier-coded. FAIL: same-site E/M and procedure without separable problem documentation.

**Approach**: single GPT-4o call per criterion (4 calls) with retrieval context. Each call: input is `ParsedEncounter` plus top-5 reranked chunks for that criterion's retrieval query. Output is a `CriterionScore` with verdict, confidence, and evidence. Overall verdict computed deterministically: any FAIL -> overall FAIL; any WEAK with no FAIL -> overall WEAK; all PASS -> overall PASS. Budget per encounter: ~15 seconds, ~$0.05 to $0.10 in API costs.

**Acceptance criteria**:

- **AC-004-1**: System MUST score all four criteria independently with cited evidence for each.
- **AC-004-2**: Overall verdict accuracy on test split (15 encounters) MUST be >=0.85 (binary: correct PASS/WEAK/FAIL vs ground truth, treating WEAK as a correct match for either PASS or FAIL ground truth, i.e., only PASS-vs-FAIL confusions count as errors).
- **AC-004-3**: Per-criterion accuracy on test split MUST be >=0.80 averaged across the four criteria.
- **AC-004-4**: Every `CriterionScore` MUST include at least one `Citation`. Empty evidence is a hard failure.
- **AC-004-5**: RAGAS faithfulness score on the analyzer's claims MUST be >=0.88.
- **AC-004-6**: Per-encounter latency MUST be p95 <20 seconds end-to-end across all four criteria.

#### EPIC-005: Compliance Guard Agent

**Why this EPIC is the architectural centerpiece**: the Compliance Guard is what makes this system production-grade rather than a demo. It implements Constitution Principle II ("Synthesis and Verification Are Architecturally Separate"). Every claim the analyzer or drafter makes is verified independently before reaching the user. If verification fails, the response is BLOCKED.

**Approach**: for each `Citation` in the response, run NLI between (premise = retrieved evidence text) and (hypothesis = the claim made about that evidence). Local inference (no API call), <500ms per claim on CPU. Threshold: claim verified if entailment probability >=0.75. **v1 verdict mapping (resolved Q2: option C)**: any flagged claim, regardless of criterion, demotes the response to BLOCKED. The DEGRADED state defined in the source design spec is deferred to v1.1; v1 UI surfaces only PASSED and BLOCKED to keep the trust story unambiguous in the demo. The data contract retains `compliance_status: "PASSED" | "BLOCKED"` only; a future v1.1 spec amendment will reintroduce DEGRADED.

**Acceptance criteria**:

- **AC-005-1**: System MUST verify every `Citation` in the `DefenderResponse` via NLI.
- **AC-005-2**: System MUST achieve 100% recall on a hand-crafted adversarial set of 20 hallucinated claims (the guard must catch every fake).
- **AC-005-3**: System MUST achieve <=10% false-positive rate on the 30-question retrieval eval set's ground-truth-correct claims (we don't want to block too many real responses).
- **AC-005-4**: BLOCKED responses MUST include structured `blocked_reasons` listing which claims failed and why.
- **AC-005-5**: Compliance check latency MUST be p95 <3 seconds for a typical response with ~8-12 citations.
- **AC-005-6**: Compliance check MUST run on every response, not sampled. No bypass.

#### EPIC-006: Remediation Drafter Agent

**Approach**: conditional, only runs when overall verdict is WEAK or FAIL. Single GPT-4o call. Input: `ParsedEncounter` + `DefensibilityAssessment` + retrieved policy chunks for each weak criterion. Output: list of `RemediationSuggestion` items, each targeting one weak criterion with specific language a clinician could add, citing the motivating policy. Suggestions MUST be marked as proposals, not edits; UI MUST render them as suggestions in a separate panel from the source note.

**Acceptance criteria**:

- **AC-006-1**: System MUST produce at least one suggestion per WEAK or FAIL criterion.
- **AC-006-2**: Each suggestion MUST cite at least one policy chunk.
- **AC-006-3**: Suggestions MUST NOT modify the source note. Output is a parallel structure, not a diff.
- **AC-006-4**: Manual review of 20 suggestions on the dev split MUST find clinical reasonableness in >=80% (a CPC-trained reviewer ideally; absent that, careful self-review against the source policies).
- **AC-006-5**: Latency: p95 <10 seconds.

#### EPIC-007: CI/CD and Quality Gates

**What runs in CI**: unit tests on agent code (pytest); schema validation tests (Pydantic) for all data contracts; retrieval recall@5 eval on the 30-question retrieval set; defensibility accuracy eval on the test split (15 encounters); compliance guard recall on the 20-claim adversarial set; RAGAS faithfulness on the test split; linting (ruff), type-checking (mypy), formatting (black); the constitutional em-dash check (no U+2014 in changed files).

**Quality gates (PR-blocking)**:

- **AC-007-1**: PR MUST fail if retrieval recall@5 <0.85.
- **AC-007-2**: PR MUST fail if overall verdict accuracy <0.85 on test split.
- **AC-007-3**: PR MUST fail if per-criterion accuracy <0.80 averaged on test split.
- **AC-007-4**: PR MUST fail if compliance guard recall <1.0 on adversarial set.
- **AC-007-5**: PR MUST fail if RAGAS faithfulness <0.88.
- **AC-007-6**: All gates MUST be enforced by GitHub Actions, not advisory.

**Out of scope**: production deployment automation (no Kubernetes, no Terraform, no managed cloud DB); continuous deployment to a staging environment.

#### EPIC-008: Demo UI

**What it shows**: single-page React app with no auth. Left panel: encounter input (textarea for note, dropdowns for E/M code, procedure code, site). Right panel: scored output with overall verdict, four criterion cards, citations clickable to highlight in source note. Below the criteria: remediation suggestions panel (only shown if WEAK or FAIL). Footer: compliance status badge (PASSED or BLOCKED), trace ID linking to Langfuse, processing time. Quality gate report viewable from a separate route (`/quality`).

**Acceptance criteria**:

- **AC-008-1**: System MUST render a complete `DefenderResponse` in <500ms after API call returns.
- **AC-008-2**: System MUST highlight cited spans in the source note when a citation is clicked.
- **AC-008-3**: System MUST show BLOCKED state distinctly (red banner, no synthesis output).
- **AC-008-4**: System MUST be screenshot-ready (clean layout, no debug clutter, fits 1440x900).
- **AC-008-5**: System MUST work on Chrome and Safari current versions.

### Key Entities (data contracts)

Reproduced verbatim from the v1 design source. TypeScript-style notation is used for clarity; the implementation uses Pydantic v2 (per Constitution).

```ts
type DefenderRequest = {
  encounter_id: string;          // synthetic ID for tracking
  note_text: string;             // raw clinical note
  em_code: string;               // e.g., "99213"
  procedure_code: string;        // e.g., "11721"
  modifier_25_attached: true;    // implicit, always true for v1
  site: "L" | "R" | "B" | null;  // left, right, bilateral, unspecified
};

type ParsedEncounter = {
  cc: TextSpan[];                 // chief complaint
  hpi: TextSpan[];                // history of present illness
  exam_findings: TextSpan[];
  mdm: TextSpan[];                // medical decision making
  procedure_note: TextSpan[];
  ambiguous_segments: TextSpan[]; // segments parser couldn't classify cleanly
};

type TextSpan = {
  text: string;
  start_char: number;
  end_char: number;
};

type DefensibilityAssessment = {
  overall: "PASS" | "WEAK" | "FAIL";
  criteria: {
    distinct_cc: CriterionScore;
    separate_exam: CriterionScore;
    independent_mdm: CriterionScore;
    site_specificity: CriterionScore;
  };
};

type CriterionScore = {
  verdict: "PASS" | "WEAK" | "FAIL";
  confidence: number;             // 0..1
  evidence: Citation[];
};

type Citation = {
  source_type: "encounter" | "policy";
  span: TextSpan;
  policy_id?: string;             // for source_type === "policy"
  rationale: string;
};

type RemediationSuggestion = {
  criterion: keyof DefensibilityAssessment["criteria"];
  suggested_addition: string;
  motivation: Citation[];         // policy citations
};

type DefenderResponse = {
  encounter_id: string;
  parsed: ParsedEncounter;
  assessment: DefensibilityAssessment;
  remediations: RemediationSuggestion[];
  compliance_status: "PASSED" | "BLOCKED";
  blocked_reasons?: string[];     // populated only when BLOCKED
  trace_id: string;               // Langfuse trace
};
```

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A coder can paste a synthetic encounter, get a scored defensibility assessment with citations, and see remediation suggestions for any weak criterion, in under 30 seconds end-to-end (p95 latency budget enforced in CI per AC-004-6 and AC-006-5).
- **SC-002**: On the test split of 15 synthetic encounters, the tool's overall verdict matches ground truth on at least 85% of cases (AC-004-2), and per-criterion accuracy averages at least 80% (AC-004-3).
- **SC-003**: On a hand-crafted adversarial set of 20 hallucinated claims, the Compliance Guard catches 100% (AC-005-2), with no more than 10% false positives on real-correct claims (AC-005-3).
- **SC-004**: A reviewer with the v1 spec and the README can reproduce every metric end-to-end from a fresh clone in under 30 minutes (Docker pull, corpus build, eval run).
- **SC-005**: Every response shown to the user carries at least one citation per criterion and a `trace_id` that resolves to a Langfuse trace replayable by an engineer (Constitution Principles I and V).
- **SC-006**: A CPC-trained reviewer (or careful self-review against the source policies) finds at least 80% of remediation suggestions clinically reasonable on a 20-encounter sample (AC-006-4).

## Assumptions

- The user is a podiatry coder familiar with E/M and procedure coding conventions; the UI does not need to teach those concepts.
- All encounter data is synthetic, generated programmatically with a fixed seed (Constitution Principle IV). No real PHI flows through the system at any point in v1.
- Reference corpus is intentionally narrow (~30 to 60 documents); broader corpus expansion is v1.1.
- LLM access is via OpenAI's API; eval reproducibility relies on a content-hash cache in `eval/.cache/`.
- The demo runs locally on Docker Compose. Cloud deployment is deferred.
- Single-user, single-tenant; no auth in v1.
- English notes only.
- Coder workflow integration is out of scope: notes arrive via paste/upload, not via direct EHR pull.
- The constitutional em-dash prohibition (Constitution coding standards) applies to all generated text in this feature, including UI strings, error messages, and downloadable reports.

## Out of Scope (v1)

- Real PHI ingestion or any HIPAA-covered data flow.
- Direct EHR integration (NextGen, eCW, ModMed). The demo accepts notes pasted or uploaded as text.
- Auto-applying remediation. The system never modifies the source note (Constitution Principle III).
- Claim submission, denial appeal, or any payer-facing action (Constitution Principle III).
- Multi-encounter or longitudinal analysis (e.g., Modifier 25 utilization rate per provider).
- Other modifiers, even when adjacent (Modifier 24, 57, 59 are deferred).
- Multi-tenant deployment. v1 is single-user demo.
- Production observability stack beyond Langfuse self-hosted.

## Deferred Backlog (v2 candidates)

- Batch mode: process a CSV of encounters in one upload.
- Provider-level utilization analytics (the >50% Pre-Payment Review trigger).
- Adjacent modifier expansion (24, 57, 59, X{EPSU}).
- Direct EHR integration via Bulk FHIR or EHI Export. Reference: see `../JARALL_EHR_Integration_Brief.docx` for NextGen and eCW integration patterns.
- Coder feedback loop: thumbs up/down on remediations, used as eval signal.

## Risk Register

- **R1: Synthetic data is too synthetic**. Generated encounters look obviously templated, undermining demo credibility with a CPC-trained reviewer. **Mitigation**: in week 1, generate 20 encounters and self-review against real podiatry note examples (publicly available redacted samples). Iterate templates if drift is obvious. Reserve a half-day in week 4 for a final pass.
- **R2: Reference corpus is thin**. 30 to 60 documents may not cover the retrieval space for nuanced scoring questions. **Mitigation**: prioritize CMS NCCI Policy Manual chapters (dense and authoritative) and JARALL's own articles. Accept that v1 may need a v1.1 corpus expansion before client-facing use.
- **R3: GPT-4o costs creep**. Defensibility Analyzer makes 4 calls per encounter. Eval runs the test split + dev split = 30 encounters * 4 calls = 120 calls per CI run, at ~$0.05 per call = $6 per CI run, plus development iteration. **Mitigation**: cache LLM responses keyed on (prompt, retrieval context) hashes during development. Only invalidate cache when prompts or retrieval changes. Estimated full project API cost: $200 to $400.
- **R4: NLI verification is too strict**. Compliance Guard blocks too many real responses, making the demo look broken. **Mitigation**: tune the entailment threshold on a held-out set of 30 verified-correct claims. Target <=10% false-positive rate (AC-005-3). If the NLI model is too conservative, swap to a more permissive equivalent (e.g., GPT-4o as a verification judge with a structured prompt).
- **R5: Solo build slips**. 3 to 4 weeks is tight for everything specified. **Mitigation (resolved Q3: option C)**: explicit cut order if behind schedule, in this order: (1) cut EPIC-008 demo polish (ship a minimal but complete UI rather than a polished one); (2) cut EPIC-006 Remediation Drafter (the analyzer's verdict alone is still demo-worthy); (3) defer reference-corpus expansion to v1.1 (run with the minimum 30 documents). NEVER cut EPIC-002 (corpus + retrieval) or EPIC-005 (Compliance Guard); those are the architectural differentiators. NEVER touch EPIC-007 quality gates: they are sacrosanct under Constitution Principle II and AC-007-6, and any change to a gate threshold requires a constitutional amendment PR. The original v1 design source suggested degrading gates to advisory under schedule pressure; that path is rejected here.
- **R6: Reviewer asks for real data**. In a follow-up, a stakeholder offers to share real client encounter notes for testing. **Mitigation**: politely decline until a BAA is in place and HIPAA-compliant data handling is implemented (out of scope for v1). This is also Constitution Principle IV.

## Definition of Done (v1)

The system is shippable for the v1 demo when:

- All 8 EPICs have all MUST acceptance criteria green.
- CI is enforcing all quality gates (no advisory mode).
- README documents architecture, setup, eval methodology, and known limitations.
- A 5-minute Loom-style video walks through the demo end-to-end.
- A written one-pager summarizes "what this is, what JARALL gets from it, what's next" for stakeholder distribution. The one-pager source is `../Modifier25_Defender_OnePager.docx`.
- Repository is publicly viewable on GitHub (or shareable via private link) per the LICENSE_PUBLIC_CONFIRM constitutional open question.
- All synthetic data and generation code is in the repo with documented methodology.
- No real PHI in any commit, ever, even in deleted commits (Constitution Principle IV).
- Constitutional em-dash check passes in CI on every PR (Constitution coding standards).

## Open Questions

The following items were carried over from the v1 design source and surface as open questions for stakeholder confirmation. Resolving any of them does not require a constitutional amendment but should update this spec.

- Does an internal Modifier 25 documentation rubric exist beyond what is in the public JARALL blog post? If so, the analyzer's criteria should match it.
- What is the average Modifier 25 utilization rate across the target client base? (Helps prioritize the eventual v2 utilization-rate analytics.)
- Which payers are most aggressive on Modifier 25 audits in the target's experience? (Payer-specific argumentation could become a future criterion.)
- Coder-facing tool (current design) vs. clinician-facing tool (suggestions surface during charting)? v1 is coder-facing; clinician-facing is a v2 conversation.

Open questions surfaced by the translation itself (not in the source):

Open questions surfaced by the translation, with their resolutions captured during spec review (Q1..Q5 round, 2026-05-03):

- **OQ-T1 (em-dash CI gate scope) [RESOLVED Q1: option C]**: the constitutional em-dash check applies to all curated text authored by humans or agents in this repo (documentation, spec, code comments, commit messages, PR descriptions, README, static UI strings). The check does NOT hard-block LLM-generated content (remediation suggestions, narrative parts of the analyzer's `rationale` fields). LLM-generated content is instead nudged via a soft instruction in the agent prompts ("avoid em-dash characters"). Implementation: the CI gate runs on changed files in `app/`, `eval/`, `ui/src/`, `docs/`, `specs/`, `*.md`, and skips outputs from runtime agents.
- **OQ-T2 (DEGRADED state in UI) [RESOLVED Q2: option C]**: v1 UI is two-state: PASSED and BLOCKED. The DEGRADED state defined in the v1 design source is deferred to v1.1. EPIC-005's verdict mapping is updated above: any flagged claim demotes the response to BLOCKED, regardless of criterion. EPIC-008 renders BLOCKED with a red banner per AC-008-3; PASSED uses standard layout. A v1.1 spec amendment will reintroduce DEGRADED with full UI requirements at that time.
- **OQ-T3 (constitutional cut-order conflict with R5) [RESOLVED Q3: option C]**: R5's mitigation has been rewritten above. New cut order is EPIC-008 polish, then EPIC-006 drafter, then defer corpus expansion to v1.1. EPIC-007 quality gates are sacrosanct; any threshold change requires a Constitution amendment PR. The original "degrade gates to advisory" path is explicitly rejected.
- **OQ-T4 (synthetic data seed) [RESOLVED Q4: option A]**: synthetic encounter generator uses seed = 42. Documented in EPIC-001 implementation tasks; the seed value is also recorded in `data/synthetic/seed.txt` for visibility.
- **OQ-T5 (eval cost cache key composition) [RESOLVED Q5: option B]**: content-hash cache key includes prompt text, retrieval context, model version, and temperature. A model upgrade or temperature change forces full re-evaluation rather than a stale cache hit. The extra API cost is accepted to prevent silent eval drift across model versions.

## Reference: v1 Design Source

This spec is a translation of:

- `../Modifier25_Defender_Spec.docx` (authoritative v1 technical specification)
- Supporting context from `../Modifier25_Defender_OnePager.docx` (executive summary)
- Supporting context from the parent `../README.md` (public-facing project README)
- Out-of-scope context from `../JARALL_EHR_Integration_Brief.docx` (informs v2 deferred backlog)

If the v1 design intent itself changes, the source documents are revised first, and a fresh spec is created (e.g., `specs/002-...`); this spec is not edited in place to reflect post-translation design changes.
