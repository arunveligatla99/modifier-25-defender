/**
 * ConnectionStatus: small indicator that surfaces whether the demo is
 * talking to a live backend or running in offline demo mode.
 */

export type ConnectionState = "checking" | "live" | "demo";

export interface ConnectionStatusProps {
  state: ConnectionState;
  url: string;
}

const DOT: Record<ConnectionState, string> = {
  checking: "bg-slate-400 animate-pulse",
  live: "bg-emerald-500",
  demo: "bg-amber-500",
};

const LABEL: Record<ConnectionState, string> = {
  checking: "Checking backend",
  live: "Live backend",
  demo: "Demo mode (offline)",
};

export function ConnectionStatus(props: ConnectionStatusProps): JSX.Element {
  return (
    <span
      className="inline-flex items-center gap-2"
      data-testid="connection-status"
      title={
        props.state === "live"
          ? props.url
          : "Backend unreachable; demo responses bundled in the UI."
      }
    >
      <span
        className={`h-2 w-2 rounded-full ${DOT[props.state]}`}
        aria-hidden="true"
      />
      <span>{LABEL[props.state]}</span>
    </span>
  );
}
