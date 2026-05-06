/**
 * CitationLink: rendered as a small chip the user can click to highlight
 * the cited span in the source note panel.
 *
 * AC-008-2: clicking a citation highlights its span in the source note.
 */

import type { Citation } from "../api/types";

export interface CitationLinkProps {
  citation: Citation;
  onClick: (citation: Citation) => void;
}

export function CitationLink(props: CitationLinkProps): JSX.Element {
  const { citation, onClick } = props;
  const label =
    citation.source_type === "policy"
      ? `policy:${citation.policy_id ?? "(unknown)"}`
      : "encounter";
  return (
    <button
      type="button"
      className="inline-flex items-center rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200"
      onClick={() => onClick(citation)}
      title={citation.rationale}
    >
      <span className="font-mono">{label}</span>
      <span className="mx-1 text-slate-400">·</span>
      <span className="max-w-xs truncate text-slate-700">
        {citation.span.text}
      </span>
    </button>
  );
}
