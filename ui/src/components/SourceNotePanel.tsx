/**
 * SourceNotePanel: renders the encounter note with a highlighted span for
 * the most recently clicked citation. AC-008-2.
 */

import type { Citation } from "../api/types";

export interface SourceNotePanelProps {
  noteText: string;
  highlight: Citation | null;
}

export function SourceNotePanel(props: SourceNotePanelProps): JSX.Element {
  const { noteText, highlight } = props;
  if (!highlight || highlight.source_type !== "encounter") {
    return (
      <pre
        className="overflow-auto whitespace-pre-wrap rounded border border-slate-200 bg-white p-4 font-mono text-sm"
        data-testid="source-note"
      >
        {noteText}
      </pre>
    );
  }
  const start = Math.max(0, Math.min(highlight.span.start_char, noteText.length));
  const end = Math.max(start, Math.min(highlight.span.end_char, noteText.length));
  const before = noteText.slice(0, start);
  const middle = noteText.slice(start, end);
  const after = noteText.slice(end);
  return (
    <pre
      className="overflow-auto whitespace-pre-wrap rounded border border-slate-200 bg-white p-4 font-mono text-sm"
      data-testid="source-note"
    >
      {before}
      <mark className="bg-yellow-200" data-testid="source-note-highlight">
        {middle}
      </mark>
      {after}
    </pre>
  );
}
