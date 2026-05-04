# Phase 1 Data Model: Modifier 25 Defender (v1 MVP)

**Feature**: `001-modifier-25-defender`
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

Entities below are reproduced from the v1 design source (TypeScript-style notation in the spec) and translated into a Pydantic v2 layout with field-level validation rules and lifecycle notes. Implementation lives under `app/schemas/`. All boundary types between agents and the API use Pydantic v2; no `dict[str, Any]` shall cross a module boundary.

## DefenderRequest

- **Purpose**: input payload accepted by `POST /analyze`.
- **Fields**:
  - `encounter_id: str` (required, non-empty, used as a synthetic ID for tracking; for synthetic data this is the hash-prefixed filename of the source encounter)
  - `note_text: str` (required, 1 to 50,000 characters; strict upper bound prevents pathological inputs from blowing past the latency budget)
  - `em_code: str` (required, must match `^9921[2-5]$` for v1; tighter validation possible if the regex is too narrow)
  - `procedure_code: str` (required, must match `^[0-9]{5}$`; semantic CPT validation deferred to runtime against a small allow-list of v1 procedure codes covered in EPIC-001)
  - `modifier_25_attached: Literal[True]` (always true for v1; field exists so that v1.1 can introduce other modifiers without a contract break)
  - `site: Literal["L", "R", "B"] | None` (optional; null when unspecified)
- **Validation rules**:
  - Note text MUST NOT contain real-PHI markers as detected by a simple denylist (real names from a known-name list, real DOB regex). On detection, return HTTP 422 with a structured error referencing Constitution Principle IV.
- **Lifecycle**: ephemeral, lives only for the duration of a single API call.

## TextSpan

- **Purpose**: reference to a span of text within either the source note or a retrieved policy chunk.
- **Fields**:
  - `text: str` (the literal text content of the span)
  - `start_char: int` (>=0)
  - `end_char: int` (> start_char)
- **Validation rules**: `text` MUST equal `source_text[start_char:end_char]` where `source_text` is the document the span refers to. The Compliance Guard verifies this invariant; a mismatch is a hard failure.

## ParsedEncounter

- **Purpose**: structured output of the Documentation Parser (EPIC-003).
- **Fields**:
  - `cc: list[TextSpan]` (chief complaint spans)
  - `hpi: list[TextSpan]` (history of present illness spans)
  - `exam_findings: list[TextSpan]`
  - `mdm: list[TextSpan]` (medical decision making spans)
  - `procedure_note: list[TextSpan]`
  - `ambiguous_segments: list[TextSpan]` (segments the parser could not classify; surfacing per AC-003-3)
- **Validation rules**:
  - The union of all field span ranges MUST be a subset of the source note character range.
  - Spans MUST NOT overlap across fields except across `ambiguous_segments` (which by definition shadows another field).
  - Schema-invalid output MUST trigger one retry per AC-003-4; second failure surfaces a structured error to the Orchestrator.

## CriterionScore

- **Purpose**: per-criterion verdict in the Defensibility Analyzer output.
- **Fields**:
  - `verdict: Literal["PASS", "WEAK", "FAIL"]`
  - `confidence: float` (0.0 <= confidence <= 1.0)
  - `evidence: list[Citation]` (MUST have length >= 1 per AC-004-4 and Constitution Principle I; empty list is a hard failure caught by the Compliance Guard).

## Citation

- **Purpose**: traceable evidence for a claim made by an agent.
- **Fields**:
  - `source_type: Literal["encounter", "policy"]`
  - `span: TextSpan`
  - `policy_id: str | None` (required when `source_type == "policy"`, references a chunk ID in the corpus; None when `source_type == "encounter"`)
  - `rationale: str` (1 to 1000 characters; the agent's reasoning linking the span to the verdict)
- **Validation rules**:
  - When `source_type == "policy"`, `policy_id` MUST resolve to an existing chunk in the active corpus snapshot.
  - The Compliance Guard verifies via NLI that the cited span entails the claim made in `rationale`.

## DefensibilityAssessment

- **Purpose**: aggregated output of the Defensibility Analyzer (EPIC-004).
- **Fields**:
  - `overall: Literal["PASS", "WEAK", "FAIL"]` (deterministic from the four sub-scores per the v1 design rule: any FAIL -> overall FAIL; any WEAK with no FAIL -> overall WEAK; all PASS -> overall PASS)
  - `criteria: CriteriaMap` (a Pydantic model with the four named fields below)
- **CriteriaMap fields**:
  - `distinct_cc: CriterionScore`
  - `separate_exam: CriterionScore`
  - `independent_mdm: CriterionScore`
  - `site_specificity: CriterionScore` (verdict MAY be "N/A" for same-site E/M-and-procedure encounters; encoded as PASS with a special `confidence = 1.0` and a single Citation pointing at the same-site finding to avoid changing the type union)
- **State transitions**: produced once per encounter; not mutable after creation.

## RemediationSuggestion

- **Purpose**: targeted documentation language drafted for a weak or failing criterion (EPIC-006).
- **Fields**:
  - `criterion: Literal["distinct_cc", "separate_exam", "independent_mdm", "site_specificity"]`
  - `suggested_addition: str` (1 to 2000 characters; clinician-facing language for the coder to suggest to the clinician)
  - `motivation: list[Citation]` (MUST have length >= 1 per AC-006-2; all citations have `source_type == "policy"`)
- **Validation rules**:
  - The Drafter MUST NOT modify the source note; this is enforced at the type level by the absence of any `note_text` field on `RemediationSuggestion`.
  - At least one suggestion per WEAK or FAIL criterion (AC-006-1).

## DefenderResponse

- **Purpose**: full response payload returned by `POST /analyze`.
- **Fields**:
  - `encounter_id: str` (echoed from request)
  - `parsed: ParsedEncounter`
  - `assessment: DefensibilityAssessment`
  - `remediations: list[RemediationSuggestion]` (empty list when overall is PASS or when EPIC-006 was cut per R5)
  - `compliance_status: Literal["PASSED", "BLOCKED"]` (two-state in v1 per Q2; v1.1 will reintroduce a third state)
  - `blocked_reasons: list[str] | None` (None when PASSED; non-empty list when BLOCKED, with each entry naming the failing claim and why)
  - `trace_id: str` (Langfuse trace ID; never None; clients use this to look up the full audit trail)
- **State transitions**: produced once per request; immutable. `compliance_status` is set by the Compliance Guard after all synthesis-side agents have completed.

## CorpusChunk (internal, not exposed at the API)

- **Purpose**: indexed unit of the reference corpus (EPIC-002).
- **Fields**:
  - `chunk_id: str` (stable across re-indexes given the same source documents)
  - `text: str` (200 to 400 tokens)
  - `source_document: str` (file name or URL)
  - `section_heading: str | None`
  - `publication_date: date | None`
  - `authority_tier: Literal["CMS", "AAPC", "JARALL", "OTHER"]`
  - `embedding: list[float]` (3072-dim, populated only in the Qdrant payload, not stored in the source-of-truth JSON)
- **Validation rules**:
  - Re-indexing is idempotent (AC-002-6); the same source documents produce the same `chunk_id`s.
  - When two chunks contradict (caught at retrieval-time by simple confidence heuristics), higher authority tier wins per the v1 design source.

## SyntheticEncounter (eval only, not exposed at the API)

- **Purpose**: a generated encounter with ground-truth labels.
- **Fields**:
  - `encounter_id: str`
  - `note_text: str`
  - `em_code: str`
  - `procedure_code: str`
  - `site: Literal["L", "R", "B"] | None`
  - `ground_truth: GroundTruthLabel`
- **GroundTruthLabel fields**:
  - `distinct_cc: Literal["PASS", "WEAK", "FAIL"]`
  - `separate_exam: Literal["PASS", "WEAK", "FAIL"]`
  - `independent_mdm: Literal["PASS", "WEAK", "FAIL"]`
  - `site_specificity: Literal["PASS", "WEAK", "FAIL"]`
  - `overall: Literal["PASS", "WEAK", "FAIL"]`
  - `parameter_space_index: dict[str, str]` (records which slot value was chosen for each of the 12 dimensions; lets the eval harness slice accuracy by dimension)
- **Lifecycle**: persisted in `data/synthetic/encounters/<encounter_id>.json` and `data/synthetic/labels.jsonl`. Regenerated deterministically by `make synthetic-data` with seed = 42.

## Module placement

| Schema | Module | Notes |
|--------|--------|-------|
| `DefenderRequest`, `DefenderResponse` | `app/schemas/api.py` | Top-level API contract |
| `TextSpan`, `Citation` | `app/schemas/text.py` | Shared primitive |
| `ParsedEncounter` | `app/schemas/parser.py` | Output of EPIC-003 |
| `CriterionScore`, `DefensibilityAssessment` | `app/schemas/assessment.py` | Output of EPIC-004 |
| `RemediationSuggestion` | `app/schemas/remediation.py` | Output of EPIC-006 |
| `CorpusChunk` | `app/schemas/corpus.py` | EPIC-002 |
| `SyntheticEncounter`, `GroundTruthLabel` | `eval/schemas.py` | Eval-only; not imported by `app/` |
