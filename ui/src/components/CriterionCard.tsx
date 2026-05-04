/**
 * CriterionCard: single criterion verdict with confidence and citation list.
 *
 * Spec EPIC-008 11.1. Color follows the verdict.* tokens in tailwind.config.ts.
 */

import type { Citation, CriterionName, CriterionScore } from "../api/types";
import { CRITERION_LABELS } from "../api/types";
import { CitationLink } from "./CitationLink";

const VERDICT_BADGE: Record<string, string> = {
  PASS: "bg-verdict-pass text-white",
  WEAK: "bg-verdict-weak text-white",
  FAIL: "bg-verdict-fail text-white",
};

export interface CriterionCardProps {
  name: CriterionName;
  score: CriterionScore;
  onCitationClick: (citation: Citation) => void;
}

export function CriterionCard(props: CriterionCardProps): JSX.Element {
  const { name, score, onCitationClick } = props;
  const badgeClass = VERDICT_BADGE[score.verdict] ?? "bg-slate-500 text-white";
  const confidencePct = Math.round(score.confidence * 100);
  return (
    <article className="rounded border border-slate-200 bg-white p-4 shadow-sm">
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-700">
          {CRITERION_LABELS[name]}
        </h3>
        <span
          className={`rounded px-2 py-0.5 text-xs font-bold ${badgeClass}`}
          aria-label={`verdict ${score.verdict}`}
        >
          {score.verdict}
        </span>
      </header>
      <p className="mt-1 text-xs text-slate-500">confidence {confidencePct}%</p>
      <ul className="mt-3 space-y-2">
        {score.evidence.map((citation, index) => (
          <li key={`${citation.source_type}-${index}`}>
            <CitationLink citation={citation} onClick={onCitationClick} />
            <p className="mt-1 text-xs text-slate-500">{citation.rationale}</p>
          </li>
        ))}
      </ul>
    </article>
  );
}
