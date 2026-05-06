/**
 * TypeScript mirrors of the backend Pydantic schemas.
 *
 * Source of truth: app/schemas/api.py and the related schema modules. When
 * the backend contract changes, both ends must change together; the eval
 * gate workflow includes a UI build step so contract drift breaks CI.
 */

export type Verdict = "PASS" | "WEAK" | "FAIL";
export type ComplianceStatus = "PASSED" | "BLOCKED";
export type Site = "L" | "R" | "B";
export type SourceType = "encounter" | "policy";
export type CriterionName =
  | "distinct_cc"
  | "separate_exam"
  | "independent_mdm"
  | "site_specificity";

export interface TextSpan {
  text: string;
  start_char: number;
  end_char: number;
}

export interface Citation {
  source_type: SourceType;
  span: TextSpan;
  policy_id: string | null;
  rationale: string;
}

export interface CriterionScore {
  verdict: Verdict;
  confidence: number;
  evidence: Citation[];
}

export interface CriteriaMap {
  distinct_cc: CriterionScore;
  separate_exam: CriterionScore;
  independent_mdm: CriterionScore;
  site_specificity: CriterionScore;
}

export interface DefensibilityAssessment {
  overall: Verdict;
  criteria: CriteriaMap;
}

export interface RemediationSuggestion {
  criterion: CriterionName;
  suggested_addition: string;
  motivation: Citation[];
}

export interface ParsedEncounter {
  cc: TextSpan[];
  hpi: TextSpan[];
  exam_findings: TextSpan[];
  mdm: TextSpan[];
  procedure_note: TextSpan[];
  ambiguous_segments: TextSpan[];
}

export interface DefenderRequest {
  encounter_id: string;
  note_text: string;
  em_code: string;
  procedure_code: string;
  modifier_25_attached: true;
  site: Site | null;
}

export interface DefenderResponse {
  encounter_id: string;
  parsed: ParsedEncounter;
  assessment: DefensibilityAssessment | null;
  remediations: RemediationSuggestion[];
  compliance_status: ComplianceStatus;
  blocked_reasons: string[] | null;
  trace_id: string;
}

export const CRITERION_LABELS: Record<CriterionName, string> = {
  distinct_cc: "Distinct CC",
  separate_exam: "Separate exam",
  independent_mdm: "Independent MDM",
  site_specificity: "Site-specificity",
};
