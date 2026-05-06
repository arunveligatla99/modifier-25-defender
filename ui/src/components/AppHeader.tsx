/**
 * AppHeader: top bar with brand mark, tagline, and connection status.
 */

import { ConnectionStatus, type ConnectionState } from "./ConnectionStatus";

export interface AppHeaderProps {
  connection: ConnectionState;
  backendUrl: string;
}

export function AppHeader(props: AppHeaderProps): JSX.Element {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div className="flex items-center gap-3">
          <div
            aria-hidden="true"
            className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-900 font-mono text-sm font-bold text-white"
          >
            M25
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900">
              Modifier 25 Defender
            </h1>
            <p className="text-xs text-slate-500">
              Documentation defensibility for podiatry coders, scored against
              the JARALL Standard.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span className="rounded border border-amber-300 bg-amber-50 px-2 py-1 font-semibold text-amber-800">
            Synthetic data only
          </span>
          <ConnectionStatus state={props.connection} url={props.backendUrl} />
        </div>
      </div>
    </header>
  );
}
