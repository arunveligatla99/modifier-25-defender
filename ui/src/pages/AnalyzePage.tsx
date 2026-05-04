/**
 * AnalyzePage: the v1 demo screen.
 *
 * Spec EPIC-008. Renders EncounterInput on the left, SourceNotePanel and
 * the four CriterionCard tiles on the right, with a BlockedBanner replacing
 * the assessment pane on BLOCKED responses (Q2 resolution: two-state UI in v1).
 */

import { useState } from "react";

import { analyzeEncounter } from "../api/client";
import type { Citation, DefenderResponse, Site } from "../api/types";
import { CRITERION_LABELS } from "../api/types";
import { BlockedBanner } from "../components/BlockedBanner";
import { CriterionCard } from "../components/CriterionCard";
import { EncounterInput } from "../components/EncounterInput";
import { SourceNotePanel } from "../components/SourceNotePanel";

const CRITERION_ORDER = [
  "distinct_cc",
  "separate_exam",
  "independent_mdm",
  "site_specificity",
] as const;

export function AnalyzePage(): JSX.Element {
  const [noteText, setNoteText] = useState("");
  const [emCode, setEmCode] = useState("99213");
  const [procedureCode, setProcedureCode] = useState("11721");
  const [site, setSite] = useState<Site | null>(null);
  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState<DefenderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<Citation | null>(null);

  const onSubmit = async (): Promise<void> => {
    setBusy(true);
    setError(null);
    setResponse(null);
    setHighlight(null);
    try {
      const r = await analyzeEncounter({
        encounter_id: `ui-${Date.now()}`,
        note_text: noteText,
        em_code: emCode,
        procedure_code: procedureCode,
        modifier_25_attached: true,
        site,
      });
      setResponse(r);
    } catch (exc) {
      const e = exc as { error?: string; reason?: string };
      setError(e.reason || e.error || "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-7xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Modifier 25 Defender
        </h1>
        <p className="text-sm text-slate-600">
          Documentation defensibility scored against the JARALL Standard.
          Synthetic data only.
        </p>
      </header>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section>
          <EncounterInput
            noteText={noteText}
            emCode={emCode}
            procedureCode={procedureCode}
            site={site}
            disabled={busy}
            onNoteChange={setNoteText}
            onEmCodeChange={setEmCode}
            onProcedureCodeChange={setProcedureCode}
            onSiteChange={setSite}
            onSubmit={onSubmit}
          />
          <SourceNotePanel noteText={noteText} highlight={highlight} />
        </section>
        <section className="space-y-4">
          {error ? (
            <p
              className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800"
              role="alert"
            >
              {error}
            </p>
          ) : null}
          {response && response.compliance_status === "BLOCKED" ? (
            <BlockedBanner reasons={response.blocked_reasons ?? []} />
          ) : null}
          {response &&
          response.compliance_status === "PASSED" &&
          response.assessment ? (
            <>
              <p className="text-sm text-slate-700">
                Overall verdict:{" "}
                <span className="font-bold">{response.assessment.overall}</span>
              </p>
              <div className="space-y-3">
                {CRITERION_ORDER.map((name) => (
                  <CriterionCard
                    key={name}
                    name={name}
                    score={response.assessment!.criteria[name]}
                    onCitationClick={(c) => setHighlight(c)}
                  />
                ))}
                {response.remediations.length > 0 ? (
                  <div className="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                    <h3 className="font-bold">Suggested remediation</h3>
                    <ul className="mt-1 list-inside list-disc space-y-1">
                      {response.remediations.map((r, i) => (
                        <li key={i}>
                          <span className="font-semibold">
                            {CRITERION_LABELS[r.criterion]}:
                          </span>{" "}
                          {r.suggested_addition}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
              <footer className="text-xs text-slate-500">
                trace_id: <span className="font-mono">{response.trace_id}</span>
              </footer>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
