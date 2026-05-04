/**
 * EncounterInput: textarea plus three dropdowns for E/M code, procedure code, and site.
 *
 * Spec EPIC-008 11.1.
 */

import { useId } from "react";
import type { Site } from "../api/types";

const EM_CODES = ["99212", "99213", "99214", "99215"] as const;
const PROCEDURE_CODES = ["11720", "11721", "11055", "11056", "11057", "20600"] as const;
const SITES: Array<{ value: Site | ""; label: string }> = [
  { value: "", label: "Unspecified" },
  { value: "L", label: "Left" },
  { value: "R", label: "Right" },
  { value: "B", label: "Bilateral" },
];

export interface EncounterInputProps {
  noteText: string;
  emCode: string;
  procedureCode: string;
  site: Site | null;
  disabled?: boolean;
  onNoteChange: (value: string) => void;
  onEmCodeChange: (value: string) => void;
  onProcedureCodeChange: (value: string) => void;
  onSiteChange: (value: Site | null) => void;
  onSubmit: () => void;
}

export function EncounterInput(props: EncounterInputProps): JSX.Element {
  const noteId = useId();
  const emId = useId();
  const procId = useId();
  const siteId = useId();
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        props.onSubmit();
      }}
    >
      <label htmlFor={noteId} className="block text-sm font-semibold text-slate-700">
        Encounter note
      </label>
      <textarea
        id={noteId}
        className="h-64 w-full rounded border border-slate-300 p-3 font-mono text-sm"
        value={props.noteText}
        disabled={props.disabled}
        onChange={(e) => props.onNoteChange(e.target.value)}
        placeholder="Paste a synthetic podiatry encounter note here..."
      />
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label htmlFor={emId} className="block text-xs font-semibold text-slate-700">
            E/M code
          </label>
          <select
            id={emId}
            className="w-full rounded border border-slate-300 p-2 text-sm"
            value={props.emCode}
            disabled={props.disabled}
            onChange={(e) => props.onEmCodeChange(e.target.value)}
          >
            {EM_CODES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={procId} className="block text-xs font-semibold text-slate-700">
            Procedure code
          </label>
          <select
            id={procId}
            className="w-full rounded border border-slate-300 p-2 text-sm"
            value={props.procedureCode}
            disabled={props.disabled}
            onChange={(e) => props.onProcedureCodeChange(e.target.value)}
          >
            {PROCEDURE_CODES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={siteId} className="block text-xs font-semibold text-slate-700">
            Site
          </label>
          <select
            id={siteId}
            className="w-full rounded border border-slate-300 p-2 text-sm"
            value={props.site ?? ""}
            disabled={props.disabled}
            onChange={(e) =>
              props.onSiteChange((e.target.value as Site | "") || null)
            }
          >
            {SITES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <button
        type="submit"
        className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
        disabled={props.disabled}
      >
        Analyze
      </button>
    </form>
  );
}
