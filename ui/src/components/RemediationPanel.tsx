/**
 * RemediationPanel: amber callout grouping remediation suggestions by
 * criterion, with policy citations under each.
 */

import type { RemediationSuggestion } from "../api/types";
import { CRITERION_LABELS } from "../api/types";

export interface RemediationPanelProps {
  suggestions: RemediationSuggestion[];
}

export function RemediationPanel(
  props: RemediationPanelProps,
): JSX.Element | null {
  if (props.suggestions.length === 0) return null;
  return (
    <section
      className="rounded-lg border border-amber-300 bg-amber-50 p-4"
      data-testid="remediation-panel"
    >
      <h2 className="flex items-center gap-2 text-sm font-bold text-amber-900">
        <span aria-hidden="true">!</span>
        Suggested documentation language
      </h2>
      <p className="mt-1 text-xs text-amber-800">
        These are clinician-facing additions you could surface to the provider.
        The Drafter never edits the source note.
      </p>
      <ul className="mt-3 space-y-3">
        {props.suggestions.map((s, i) => (
          <li key={i} className="rounded border border-amber-200 bg-white p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
              {CRITERION_LABELS[s.criterion]}
            </p>
            <p className="mt-1 text-sm text-slate-800">
              {s.suggested_addition}
            </p>
            {s.motivation.length > 0 ? (
              <details className="mt-2 text-xs text-slate-600">
                <summary className="cursor-pointer text-amber-800 hover:underline">
                  Policy basis ({s.motivation.length})
                </summary>
                <ul className="mt-2 space-y-1">
                  {s.motivation.map((m, j) => (
                    <li key={j} className="rounded bg-amber-50/60 p-2">
                      <p className="font-mono text-[11px] text-slate-500">
                        {m.policy_id ?? "policy"}
                      </p>
                      <p className="mt-0.5 italic text-slate-700">
                        "{m.span.text}"
                      </p>
                      <p className="mt-1 text-slate-600">{m.rationale}</p>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
