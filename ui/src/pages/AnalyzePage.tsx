/**
 * AnalyzePage: the v1 demo screen.
 *
 * Layout (desktop):
 *
 *   AppHeader
 *   ┌───────────────────────────────────────────────────────────┐
 *   │  SampleLoader                                              │
 *   ├──────────────────────────────┬─────────────────────────────┤
 *   │  EncounterInput              │  OverallVerdict             │
 *   │  SourceNotePanel             │  CriterionCard x 4 (2x2)    │
 *   │                              │  RemediationPanel           │
 *   └──────────────────────────────┴─────────────────────────────┘
 *
 * Demo mode: when the backend is unreachable, we fall back to canned
 * responses bundled in src/fixtures/sampleEncounters.ts. The connection
 * indicator in the header makes this state explicit so the demo is
 * never quietly serving stale data.
 *
 * Spec: EPIC-008. AC-008-2 (citation click highlights span), AC-008-3
 * (BLOCKED state visually distinct from PASSED).
 */

import { useEffect, useState } from "react";

import { analyzeEncounter, backendUrl, pingBackend } from "../api/client";
import type { Citation, DefenderResponse, Site } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { BlockedBanner } from "../components/BlockedBanner";
import type { ConnectionState } from "../components/ConnectionStatus";
import { CriterionCard } from "../components/CriterionCard";
import { EncounterInput } from "../components/EncounterInput";
import { OverallVerdict } from "../components/OverallVerdict";
import { RemediationPanel } from "../components/RemediationPanel";
import { SampleLoader } from "../components/SampleLoader";
import { SourceNotePanel } from "../components/SourceNotePanel";
import {
  findSampleByRequest,
  type SampleEncounter,
} from "../fixtures/sampleEncounters";

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
  const [activeSampleId, setActiveSampleId] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState<DefenderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<Citation | null>(null);

  const [connection, setConnection] = useState<ConnectionState>("checking");
  const url = backendUrl();

  useEffect(() => {
    let cancelled = false;
    pingBackend()
      .then((ok) => {
        if (!cancelled) setConnection(ok ? "live" : "demo");
      })
      .catch(() => {
        if (!cancelled) setConnection("demo");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onLoadSample = (sample: SampleEncounter): void => {
    setNoteText(sample.request.note_text);
    setEmCode(sample.request.em_code);
    setProcedureCode(sample.request.procedure_code);
    setSite(sample.request.site);
    setActiveSampleId(sample.id);
    setResponse(null);
    setError(null);
    setHighlight(null);
  };

  const onSubmit = async (): Promise<void> => {
    setBusy(true);
    setError(null);
    setResponse(null);
    setHighlight(null);
    const request = {
      encounter_id: `ui-${Date.now()}`,
      note_text: noteText,
      em_code: emCode,
      procedure_code: procedureCode,
      modifier_25_attached: true as const,
      site,
    };
    try {
      if (connection === "demo") {
        // Bundled fallback: serve the canned response when the input
        // matches one of the sample encounters; otherwise the user must
        // start the backend.
        const sample = findSampleByRequest(request);
        if (!sample) {
          throw {
            error: "demo_no_match",
            reason:
              "Backend unreachable and the entered note does not match a bundled sample. Start the backend or use a sample button above.",
          };
        }
        // Tiny artificial delay so the UI feels responsive.
        await new Promise((r) => setTimeout(r, 300));
        setResponse(sample.response);
      } else {
        const r = await analyzeEncounter(request);
        setResponse(r);
      }
    } catch (exc) {
      const e = exc as { error?: string; reason?: string };
      setError(e.reason || e.error || "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader connection={connection} backendUrl={url} />
      <main className="mx-auto max-w-7xl space-y-4 p-6">
        <SampleLoader
          onLoad={onLoadSample}
          disabled={busy}
          activeId={activeSampleId}
        />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <section className="space-y-4">
            <EncounterInput
              noteText={noteText}
              emCode={emCode}
              procedureCode={procedureCode}
              site={site}
              disabled={busy}
              onNoteChange={(v) => {
                setNoteText(v);
                setActiveSampleId(null);
              }}
              onEmCodeChange={setEmCode}
              onProcedureCodeChange={setProcedureCode}
              onSiteChange={setSite}
              onSubmit={onSubmit}
            />
            <SourceNotePanel noteText={noteText} highlight={highlight} />
          </section>
          <section className="space-y-4">
            {busy ? (
              <p
                className="rounded border border-slate-200 bg-white p-3 text-sm text-slate-600"
                data-testid="busy-banner"
              >
                Running parser, analyzer, and Compliance Guard...
              </p>
            ) : null}
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
                <OverallVerdict
                  verdict={response.assessment.overall}
                  criteria={response.assessment.criteria}
                />
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {CRITERION_ORDER.map((name) => (
                    <CriterionCard
                      key={name}
                      name={name}
                      score={response.assessment!.criteria[name]}
                      onCitationClick={(c) => setHighlight(c)}
                    />
                  ))}
                </div>
                <RemediationPanel suggestions={response.remediations} />
                <footer className="text-xs text-slate-500">
                  trace_id:{" "}
                  <span className="font-mono">{response.trace_id}</span>
                </footer>
              </>
            ) : null}
            {!response && !busy && !error ? (
              <p className="rounded border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
                Load a sample above or paste a synthetic note, then click
                Analyze. Results appear here.
              </p>
            ) : null}
          </section>
        </div>
      </main>
    </div>
  );
}
