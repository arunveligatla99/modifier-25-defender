/**
 * SampleLoader: three buttons that load the bundled PASS / WEAK / FAIL
 * sample encounters into the EncounterInput. Useful for live demos.
 */

import {
  SAMPLE_ENCOUNTERS,
  type SampleEncounter,
} from "../fixtures/sampleEncounters";

const VERDICT_BADGE: Record<SampleEncounter["expectedVerdict"], string> = {
  PASS: "bg-emerald-100 text-emerald-800 border-emerald-200",
  WEAK: "bg-amber-100 text-amber-800 border-amber-200",
  FAIL: "bg-rose-100 text-rose-800 border-rose-200",
};

export interface SampleLoaderProps {
  onLoad: (sample: SampleEncounter) => void;
  disabled?: boolean;
  activeId: string | null;
}

export function SampleLoader(props: SampleLoaderProps): JSX.Element {
  return (
    <section
      className="rounded border border-slate-200 bg-white p-3"
      aria-label="Sample encounters"
    >
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Try a sample encounter
      </h2>
      <p className="mt-1 text-xs text-slate-500">
        Synthetic notes generated from the eval test/dev split. Click one to
        load it and run the analyzer.
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {SAMPLE_ENCOUNTERS.map((sample) => {
          const active = props.activeId === sample.id;
          return (
            <button
              key={sample.id}
              type="button"
              disabled={props.disabled}
              onClick={() => props.onLoad(sample)}
              className={[
                "rounded border p-3 text-left text-xs transition disabled:opacity-50",
                active
                  ? "border-slate-900 bg-slate-50"
                  : "border-slate-200 bg-white hover:border-slate-400 hover:bg-slate-50",
              ].join(" ")}
              data-testid={`sample-load-${sample.expectedVerdict.toLowerCase()}`}
            >
              <span
                className={`inline-block rounded-full border px-2 py-0.5 font-bold ${VERDICT_BADGE[sample.expectedVerdict]}`}
              >
                {sample.expectedVerdict}
              </span>
              <p className="mt-2 font-medium text-slate-800">{sample.label}</p>
              <p className="mt-1 font-mono text-slate-500">
                E/M {sample.request.em_code} / {sample.request.procedure_code}
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
}
