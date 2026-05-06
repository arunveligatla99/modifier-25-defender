/**
 * OverallVerdict: hero card summarizing the assessment. Big verdict pill,
 * one-line interpretation, criterion roll-up.
 */

import type { CriteriaMap, Verdict } from "../api/types";

const VERDICT_BG: Record<Verdict, string> = {
  PASS: "bg-emerald-50 border-emerald-200",
  WEAK: "bg-amber-50 border-amber-200",
  FAIL: "bg-rose-50 border-rose-200",
};

const VERDICT_PILL: Record<Verdict, string> = {
  PASS: "bg-verdict-pass text-white",
  WEAK: "bg-verdict-weak text-white",
  FAIL: "bg-verdict-fail text-white",
};

const VERDICT_BLURB: Record<Verdict, string> = {
  PASS: "Documentation is defensible across all four JARALL criteria.",
  WEAK: "Documentation is borderline. Strengthen the flagged criteria before billing.",
  FAIL: "Documentation does not support modifier 25. See remediation below.",
};

export interface OverallVerdictProps {
  verdict: Verdict;
  criteria: CriteriaMap;
}

const NAMES = [
  "distinct_cc",
  "separate_exam",
  "independent_mdm",
  "site_specificity",
] as const;
const SHORT: Record<(typeof NAMES)[number], string> = {
  distinct_cc: "CC",
  separate_exam: "Exam",
  independent_mdm: "MDM",
  site_specificity: "Site",
};

export function OverallVerdict(props: OverallVerdictProps): JSX.Element {
  const { verdict, criteria } = props;
  return (
    <section
      className={`rounded-lg border p-5 ${VERDICT_BG[verdict]}`}
      data-testid="overall-verdict"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Overall verdict
          </p>
          <p className="mt-1 text-sm text-slate-700">
            {VERDICT_BLURB[verdict]}
          </p>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-4 py-1.5 text-base font-bold ${VERDICT_PILL[verdict]}`}
          aria-label={`overall ${verdict}`}
        >
          {verdict}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {NAMES.map((name) => {
          const v = criteria[name].verdict;
          return (
            <div
              key={name}
              className="rounded border border-white/60 bg-white/70 px-3 py-2"
            >
              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                {SHORT[name]}
              </p>
              <p
                className={`mt-0.5 text-sm font-bold ${
                  v === "PASS"
                    ? "text-verdict-pass"
                    : v === "WEAK"
                      ? "text-verdict-weak"
                      : "text-verdict-fail"
                }`}
              >
                {v}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
