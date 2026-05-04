# Contract: POST /analyze

**Feature**: `001-modifier-25-defender`
**Service**: FastAPI backend at `app/api/`
**Endpoint**: `POST /analyze`
**Authentication**: none (v1 demo)

## Purpose

Score an encounter's defensibility against the four JARALL Standard criteria, surfacing citations and remediation suggestions, with all output verified by the Compliance Guard before the response is returned.

## Request

- **Method**: `POST`
- **Path**: `/analyze`
- **Content-Type**: `application/json`
- **Body**: `DefenderRequest` (see [data-model.md](../data-model.md))

```json
{
  "encounter_id": "synth_20260503_001",
  "note_text": "CC: thick painful nails. HPI: 6 months of nail thickening...",
  "em_code": "99213",
  "procedure_code": "11721",
  "modifier_25_attached": true,
  "site": "B"
}
```

### Request validation

- `encounter_id`: non-empty string.
- `note_text`: 1 to 50,000 characters. PHI detection runs before any agent is invoked; if a real-PHI marker is found, return `422 Unprocessable Entity` with body `{ "error": "phi_detected", "reason": "..." }`. No agent runs on PHI-positive input.
- `em_code`: matches `^9921[2-5]$`.
- `procedure_code`: matches `^[0-9]{5}$` and is in the v1 allow-list (defined in `data/procedure_codes_allowlist.json`, populated by EPIC-001 task).
- `modifier_25_attached`: must be `true`.
- `site`: one of `"L"`, `"R"`, `"B"`, or absent/null.

## Response (success)

- **Status**: `200 OK`
- **Content-Type**: `application/json`
- **Body**: `DefenderResponse`

```json
{
  "encounter_id": "synth_20260503_001",
  "parsed": { "cc": [...], "hpi": [...], "exam_findings": [...], "mdm": [...], "procedure_note": [...], "ambiguous_segments": [] },
  "assessment": {
    "overall": "FAIL",
    "criteria": {
      "distinct_cc": { "verdict": "FAIL", "confidence": 0.94, "evidence": [{ "source_type": "encounter", "span": { "text": "thick painful nails", "start_char": 4, "end_char": 23 }, "rationale": "CC names the procedure indication, not a separate problem.", "policy_id": null }] },
      "separate_exam": { "verdict": "FAIL", "confidence": 0.91, "evidence": [...] },
      "independent_mdm": { "verdict": "FAIL", "confidence": 0.88, "evidence": [...] },
      "site_specificity": { "verdict": "PASS", "confidence": 1.0, "evidence": [...] }
    }
  },
  "remediations": [
    { "criterion": "distinct_cc", "suggested_addition": "Document a separately identifiable problem in the chief complaint, e.g., new heel pain, prior to the nail-debridement workup.", "motivation": [{ "source_type": "policy", "span": { "text": "...", "start_char": 0, "end_char": 100 }, "policy_id": "cms-ncci-em-modifier25-2026-ch1-sec3", "rationale": "CMS NCCI Policy Manual: a separately identifiable E/M service must be supported by a distinct problem." }] }
  ],
  "compliance_status": "PASSED",
  "blocked_reasons": null,
  "trace_id": "lf_t_01HXYZ..."
}
```

## Response (BLOCKED)

When the Compliance Guard fails one or more entailment checks, the response is BLOCKED. Per Q2 resolution, v1 does not surface a DEGRADED state.

```json
{
  "encounter_id": "synth_20260503_001",
  "parsed": { ... },
  "assessment": null,
  "remediations": [],
  "compliance_status": "BLOCKED",
  "blocked_reasons": [
    "criterion=independent_mdm: claim 'MDM addresses a separate problem' not entailed by cited span 'discussed risks/benefits of debridement, patient consents'."
  ],
  "trace_id": "lf_t_01HXYZ..."
}
```

Note: when BLOCKED, `assessment` is null and `remediations` is empty. The `parsed` field may be returned to help the coder see how their note was interpreted, since the parser stage is upstream of the Compliance Guard.

## Response (errors)

- **`400 Bad Request`**: schema-invalid request (e.g., `em_code` missing or wrong format). Body: `{ "error": "validation", "details": [ ... ] }` matching FastAPI's default validation error shape.
- **`422 Unprocessable Entity`**: PHI detected in `note_text` or `procedure_code` not in v1 allow-list. Body: `{ "error": "phi_detected" | "procedure_code_unsupported", "reason": "..." }`.
- **`500 Internal Server Error`**: unexpected agent failure (e.g., LLM API outage, schema-invalid agent output after one retry). Body: `{ "error": "agent_failure", "agent": "parser" | "analyzer" | "drafter" | "compliance_guard", "trace_id": "lf_t_..." }`. The `trace_id` is always returned so a coder or engineer can dig in.

## Latency contract

- p50 < 12 seconds end-to-end on a synthetic encounter.
- p95 < 30 seconds end-to-end (composed budget per AC-003-5, AC-004-6, AC-005-5, AC-006-5; sum-of-budgets is conservative because the agents run sequentially in v1, not in parallel).

## Idempotency

`POST /analyze` is idempotent for a given `(encounter_id, note_text, em_code, procedure_code, site)` tuple, modulo LLM nondeterminism (which is bounded by `temperature=0` in v1 and the eval cache for repeated test runs).

## Observability

Every response carries a `trace_id` referencing a Langfuse trace that contains: the `DefenderRequest`, the parser's prompt + response, the analyzer's per-criterion prompt + retrieved chunks + response, the drafter's prompt + response (if invoked), the compliance guard's NLI inputs and per-claim verdicts, and the final `DefenderResponse`. Replay is supported (Constitution Principle V).
