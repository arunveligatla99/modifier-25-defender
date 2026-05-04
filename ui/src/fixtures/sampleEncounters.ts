/**
 * Demo-mode sample encounters with canned DefenderResponses.
 *
 * The notes are taken verbatim from the synthetic test/dev split so they
 * round-trip cleanly through the parser at the offsets cited below. The
 * canned responses match what the live pipeline produces against these
 * encounters at gpt-4o + DeBERTa NLI; they are bundled in the UI so the
 * demo works without a backend.
 */

import type { DefenderResponse, DefenderRequest, Site } from "../api/types";

export interface SampleEncounter {
  id: string;
  label: string;
  expectedVerdict: "PASS" | "WEAK" | "FAIL";
  request: DefenderRequest;
  response: DefenderResponse;
}

const PASS_NOTE = `CC: hallux MTP pain with new midfoot stiffness

HPI: weeks of symptoms relating to multiple thickened painful nails. Patient also reports a distinct symptom requiring separate evaluation.

Exam: nails examined consistent with multiple thickened painful nails. Separately identified: tenderness at a distinct anatomic location with documented quality, palpable swelling, and pain on resisted motion.

MDM: addressed an independent problem with risks, data review (X-ray pending), and a management plan distinct from the procedure decision; shared decision making documented.

Procedure: Debridement of 6 or more thickened nails performed with sterile technique (LT and RT modifiers documented). Tolerated well, no immediate complications.`;

const WEAK_NOTE = `CC: hallux MTP pain with new midfoot stiffness
HPI: weeks of symptoms relating to painful plantar callus. Patient also reports a distinct symptom requiring separate evaluation. PMH: Type 2 diabetes mellitus. Sensory neuropathy noted on prior visits.
Exam: plantar callus area consistent with painful plantar callus. Additional finding: mild tenderness at a separate site.
MDM: addressed the procedure as well as a separate complaint; considered conservative options for the separate complaint and deferred a decision.
Procedure: Paring of single hyperkeratotic lesion performed (LT modifier documented). Tolerated well, no immediate complications.`;

const FAIL_NOTE = `CC: hallux MTP pain

HPI: weeks of symptoms relating to first MTP joint inflammation with refractory pain. PMH: Type 2 diabetes mellitus. Sensory neuropathy noted on prior visits.

Exam: first MTP joint consistent with first MTP joint inflammation with refractory pain; general inspection of the foot otherwise unremarkable.

MDM: addressed an independent problem with risks, data review (X-ray pending), and a management plan distinct from the procedure decision; shared decision making documented.

Procedure: Aspiration and corticosteroid injection of the first MTP joint performed (LT and RT modifiers documented). Tolerated well, no immediate complications.`;

function findOffset(
  haystack: string,
  needle: string,
): { start: number; end: number } {
  const start = haystack.indexOf(needle);
  if (start === -1) {
    throw new Error(`fixture span not found: "${needle.slice(0, 60)}..."`);
  }
  return { start, end: start + needle.length };
}

function span(note: string, text: string) {
  const { start, end } = findOffset(note, text);
  return { text, start_char: start, end_char: end };
}

function buildRequest(
  id: string,
  note: string,
  emCode: string,
  procedureCode: string,
  site: Site | null,
): DefenderRequest {
  return {
    encounter_id: id,
    note_text: note,
    em_code: emCode,
    procedure_code: procedureCode,
    modifier_25_attached: true,
    site,
  };
}

const passResponse: DefenderResponse = {
  encounter_id: "demo-pass",
  parsed: {
    cc: [span(PASS_NOTE, "hallux MTP pain with new midfoot stiffness")],
    hpi: [
      span(
        PASS_NOTE,
        "weeks of symptoms relating to multiple thickened painful nails. Patient also reports a distinct symptom requiring separate evaluation.",
      ),
    ],
    exam_findings: [
      span(
        PASS_NOTE,
        "nails examined consistent with multiple thickened painful nails. Separately identified: tenderness at a distinct anatomic location with documented quality, palpable swelling, and pain on resisted motion.",
      ),
    ],
    mdm: [
      span(
        PASS_NOTE,
        "addressed an independent problem with risks, data review (X-ray pending), and a management plan distinct from the procedure decision; shared decision making documented.",
      ),
    ],
    procedure_note: [
      span(
        PASS_NOTE,
        "Debridement of 6 or more thickened nails performed with sterile technique (LT and RT modifiers documented). Tolerated well, no immediate complications.",
      ),
    ],
    ambiguous_segments: [],
  },
  assessment: {
    overall: "PASS",
    criteria: {
      distinct_cc: {
        verdict: "PASS",
        confidence: 0.92,
        evidence: [
          {
            source_type: "encounter",
            span: span(PASS_NOTE, "hallux MTP pain with new midfoot stiffness"),
            policy_id: null,
            rationale:
              "Chief complaint names a problem (midfoot stiffness) distinct from the procedure indication (thickened nails).",
          },
        ],
      },
      separate_exam: {
        verdict: "PASS",
        confidence: 0.94,
        evidence: [
          {
            source_type: "encounter",
            span: span(
              PASS_NOTE,
              "tenderness at a distinct anatomic location with documented quality, palpable swelling, and pain on resisted motion",
            ),
            policy_id: null,
            rationale:
              "Exam documents specific findings on an anatomic location distinct from the nail debridement site.",
          },
        ],
      },
      independent_mdm: {
        verdict: "PASS",
        confidence: 0.9,
        evidence: [
          {
            source_type: "encounter",
            span: span(
              PASS_NOTE,
              "addressed an independent problem with risks, data review (X-ray pending), and a management plan distinct from the procedure decision",
            ),
            policy_id: null,
            rationale:
              "MDM documents an independent problem with risks, data review, and a concrete management plan distinct from the procedure.",
          },
        ],
      },
      site_specificity: {
        verdict: "PASS",
        confidence: 0.95,
        evidence: [
          {
            source_type: "encounter",
            span: span(PASS_NOTE, "(LT and RT modifiers documented)"),
            policy_id: null,
            rationale:
              "Procedure note explicitly documents both LT and RT modifiers, matching the bilateral encounter site.",
          },
        ],
      },
    },
  },
  remediations: [],
  compliance_status: "PASSED",
  blocked_reasons: null,
  trace_id: "demo-trace-pass-0001",
};

const weakResponse: DefenderResponse = {
  encounter_id: "demo-weak",
  parsed: {
    cc: [span(WEAK_NOTE, "hallux MTP pain with new midfoot stiffness")],
    hpi: [
      span(
        WEAK_NOTE,
        "weeks of symptoms relating to painful plantar callus. Patient also reports a distinct symptom requiring separate evaluation. PMH: Type 2 diabetes mellitus. Sensory neuropathy noted on prior visits.",
      ),
    ],
    exam_findings: [
      span(
        WEAK_NOTE,
        "plantar callus area consistent with painful plantar callus. Additional finding: mild tenderness at a separate site.",
      ),
    ],
    mdm: [
      span(
        WEAK_NOTE,
        "addressed the procedure as well as a separate complaint; considered conservative options for the separate complaint and deferred a decision.",
      ),
    ],
    procedure_note: [
      span(
        WEAK_NOTE,
        "Paring of single hyperkeratotic lesion performed (LT modifier documented). Tolerated well, no immediate complications.",
      ),
    ],
    ambiguous_segments: [],
  },
  assessment: {
    overall: "WEAK",
    criteria: {
      distinct_cc: {
        verdict: "PASS",
        confidence: 0.86,
        evidence: [
          {
            source_type: "encounter",
            span: span(WEAK_NOTE, "hallux MTP pain with new midfoot stiffness"),
            policy_id: null,
            rationale:
              "Chief complaint names midfoot stiffness, distinct from the callus-paring indication.",
          },
        ],
      },
      separate_exam: {
        verdict: "WEAK",
        confidence: 0.78,
        evidence: [
          {
            source_type: "encounter",
            span: span(
              WEAK_NOTE,
              "Additional finding: mild tenderness at a separate site",
            ),
            policy_id: null,
            rationale:
              "Exam mentions a non-procedure finding but it is generic. Specificity (location, quality, palpation) is missing.",
          },
        ],
      },
      independent_mdm: {
        verdict: "WEAK",
        confidence: 0.72,
        evidence: [
          {
            source_type: "encounter",
            span: span(
              WEAK_NOTE,
              "considered conservative options for the separate complaint and deferred a decision",
            ),
            policy_id: null,
            rationale:
              "MDM mentions a separate complaint but no concrete action is taken today; the decision is deferred.",
          },
        ],
      },
      site_specificity: {
        verdict: "PASS",
        confidence: 0.88,
        evidence: [
          {
            source_type: "encounter",
            span: span(WEAK_NOTE, "(LT modifier documented)"),
            policy_id: null,
            rationale: "LT modifier matches the recorded left-side procedure.",
          },
        ],
      },
    },
  },
  remediations: [
    {
      criterion: "separate_exam",
      suggested_addition:
        "Document the separate finding with specifics: anatomic location (e.g., midfoot dorsum), quality of tenderness on palpation, presence or absence of swelling, and any provocation maneuver result.",
      motivation: [
        {
          source_type: "policy",
          span: {
            text: "Exam findings must include observations on at least one body part or condition that is not the procedure site.",
            start_char: 0,
            end_char: 110,
          },
          policy_id: "aapc-modifier25-mastery-2026.txt|46557c1b9929",
          rationale:
            "Policy requires specific exam findings outside the procedure site; generic mentions are not sufficient.",
        },
      ],
    },
    {
      criterion: "independent_mdm",
      suggested_addition:
        "Document a concrete action taken today for the separate complaint: a specific medication started, imaging ordered, brace prescribed, follow-up scheduled, or shared decision making documented.",
      motivation: [
        {
          source_type: "policy",
          span: {
            text: "The medical decision making must reflect an independent judgment with risks, data review, and a management plan distinct from the procedure decision.",
            start_char: 0,
            end_char: 158,
          },
          policy_id: "aapc-modifier25-mastery-2026.txt|46557c1b9929",
          rationale:
            "Policy requires a concrete management plan today, not deferral or vague consideration of options.",
        },
      ],
    },
  ],
  compliance_status: "PASSED",
  blocked_reasons: null,
  trace_id: "demo-trace-weak-0001",
};

const failResponse: DefenderResponse = {
  encounter_id: "demo-fail",
  parsed: {
    cc: [span(FAIL_NOTE, "hallux MTP pain")],
    hpi: [
      span(
        FAIL_NOTE,
        "weeks of symptoms relating to first MTP joint inflammation with refractory pain. PMH: Type 2 diabetes mellitus. Sensory neuropathy noted on prior visits.",
      ),
    ],
    exam_findings: [
      span(
        FAIL_NOTE,
        "first MTP joint consistent with first MTP joint inflammation with refractory pain; general inspection of the foot otherwise unremarkable.",
      ),
    ],
    mdm: [
      span(
        FAIL_NOTE,
        "addressed an independent problem with risks, data review (X-ray pending), and a management plan distinct from the procedure decision; shared decision making documented.",
      ),
    ],
    procedure_note: [
      span(
        FAIL_NOTE,
        "Aspiration and corticosteroid injection of the first MTP joint performed (LT and RT modifiers documented). Tolerated well, no immediate complications.",
      ),
    ],
    ambiguous_segments: [],
  },
  assessment: {
    overall: "FAIL",
    criteria: {
      distinct_cc: {
        verdict: "FAIL",
        confidence: 0.91,
        evidence: [
          {
            source_type: "encounter",
            span: span(FAIL_NOTE, "hallux MTP pain"),
            policy_id: null,
            rationale:
              "Chief complaint reads as the procedure indication (first MTP joint pain) with no separable problem named.",
          },
        ],
      },
      separate_exam: {
        verdict: "FAIL",
        confidence: 0.89,
        evidence: [
          {
            source_type: "encounter",
            span: span(
              FAIL_NOTE,
              "general inspection of the foot otherwise unremarkable",
            ),
            policy_id: null,
            rationale:
              "Exam findings are limited to the procedure site; no specific finding outside the first MTP joint is documented.",
          },
        ],
      },
      independent_mdm: {
        verdict: "PASS",
        confidence: 0.84,
        evidence: [
          {
            source_type: "encounter",
            span: span(
              FAIL_NOTE,
              "addressed an independent problem with risks, data review (X-ray pending), and a management plan distinct from the procedure decision",
            ),
            policy_id: null,
            rationale:
              "MDM documents an independent problem with concrete management plan distinct from the procedure.",
          },
        ],
      },
      site_specificity: {
        verdict: "PASS",
        confidence: 0.93,
        evidence: [
          {
            source_type: "encounter",
            span: span(FAIL_NOTE, "(LT and RT modifiers documented)"),
            policy_id: null,
            rationale:
              "Bilateral encounter with both LT and RT modifiers documented in procedure note.",
          },
        ],
      },
    },
  },
  remediations: [
    {
      criterion: "distinct_cc",
      suggested_addition:
        "Add a chief complaint that names a problem distinct from the procedure indication. For example, document the diabetes/neuropathy follow-up concern, a contralateral pain, or a new functional limitation that motivated the visit beyond the joint injection.",
      motivation: [
        {
          source_type: "policy",
          span: {
            text: "The chief complaint must name a problem distinct from the procedure's primary indication.",
            start_char: 0,
            end_char: 92,
          },
          policy_id: "jarall-modifier25-mastery-2026-04-23.txt|2fee59e3ad80",
          rationale:
            "Policy is explicit: a CC that reads as the procedure indication does not support modifier 25.",
        },
      ],
    },
    {
      criterion: "separate_exam",
      suggested_addition:
        "Document a specific exam finding outside the first MTP joint: assess circulation and sensation given the diabetic/neuropathic history, palpate other foot structures, or document any incidental finding with quality and location.",
      motivation: [
        {
          source_type: "policy",
          span: {
            text: "Exam findings must include observations on at least one body part or condition that is not the procedure site.",
            start_char: 0,
            end_char: 110,
          },
          policy_id: "aapc-modifier25-mastery-2026.txt|46557c1b9929",
          rationale:
            "Policy requires findings outside the procedure site; 'otherwise unremarkable' fails the criterion.",
        },
      ],
    },
  ],
  compliance_status: "PASSED",
  blocked_reasons: null,
  trace_id: "demo-trace-fail-0001",
};

export const SAMPLE_ENCOUNTERS: SampleEncounter[] = [
  {
    id: "demo-pass",
    label: "PASS: bilateral nail debridement with separate finding",
    expectedVerdict: "PASS",
    request: buildRequest("demo-pass", PASS_NOTE, "99214", "11721", "B"),
    response: passResponse,
  },
  {
    id: "demo-weak",
    label: "WEAK: callus paring with vague separate finding",
    expectedVerdict: "WEAK",
    request: buildRequest("demo-weak", WEAK_NOTE, "99212", "11055", "L"),
    response: weakResponse,
  },
  {
    id: "demo-fail",
    label: "FAIL: joint injection, no distinct documentation",
    expectedVerdict: "FAIL",
    request: buildRequest("demo-fail", FAIL_NOTE, "99213", "20600", "B"),
    response: failResponse,
  },
];

export function findSampleByRequest(
  req: DefenderRequest,
): SampleEncounter | undefined {
  return SAMPLE_ENCOUNTERS.find((s) => s.request.note_text === req.note_text);
}
