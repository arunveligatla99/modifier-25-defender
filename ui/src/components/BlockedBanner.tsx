/**
 * BlockedBanner: red banner shown for BLOCKED responses with structured reasons.
 *
 * AC-008-3: BLOCKED state must be visually distinct from PASSED.
 */

export interface BlockedBannerProps {
  reasons: string[];
}

export function BlockedBanner(props: BlockedBannerProps): JSX.Element {
  return (
    <section
      className="rounded border border-red-300 bg-red-50 p-4"
      role="alert"
      aria-label="Compliance Guard blocked the response"
      data-testid="blocked-banner"
    >
      <h2 className="text-sm font-bold text-red-800">
        BLOCKED by Compliance Guard
      </h2>
      <p className="mt-1 text-xs text-red-700">
        The response was blocked because one or more cited claims could not be
        verified against the cited evidence. Synthesis output is not shown.
      </p>
      <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-red-900">
        {props.reasons.map((reason, index) => (
          <li key={index} className="font-mono">
            {reason}
          </li>
        ))}
      </ul>
    </section>
  );
}
