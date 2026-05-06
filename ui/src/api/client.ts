/**
 * Typed POST /analyze client with demo-mode fallback.
 *
 * Default backendUrl() is empty so the UI issues SAME-ORIGIN requests
 * to /healthz and /analyze. The Vite dev server (see ui/vite.config.ts)
 * proxies those paths to the FastAPI backend on localhost:8000. This
 * lets the UI work behind an https tunnel (e.g. ngrok) without hitting
 * mixed-content blocks or CORS preflight failures, because the browser
 * never sees a cross-origin URL. Set VITE_BACKEND_URL in production
 * deployments where the backend lives at a different absolute origin.
 *
 * Demo: when the backend is unreachable at the network layer, the
 * AnalyzePage falls back to canned responses bundled in
 * src/fixtures/sampleEncounters.ts so the UI is usable for live demos
 * without infra.
 *
 * The fetcher is injectable for unit tests.
 */

import type { DefenderRequest, DefenderResponse } from "./types";

export interface AnalyzeError {
  status: number;
  error: string;
  reason?: string;
  details?: unknown;
}

export type FetchLike = typeof fetch;

const DEFAULT_BACKEND_URL = "";

export function backendUrl(): string {
  const env = typeof import.meta !== "undefined" ? import.meta.env : undefined;
  const configured = env?.VITE_BACKEND_URL;
  if (typeof configured === "string") return configured;
  return DEFAULT_BACKEND_URL;
}

export async function analyzeEncounter(
  request: DefenderRequest,
  options: { fetcher?: FetchLike; backendOverride?: string } = {},
): Promise<DefenderResponse> {
  const fetcher = options.fetcher ?? fetch;
  const url = `${options.backendOverride ?? backendUrl()}/analyze`;
  const resp = await fetcher(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw {
      status: resp.status,
      error: detail.error ?? "request_failed",
      reason: detail.reason,
      details: detail.details,
    } satisfies AnalyzeError;
  }
  return (await resp.json()) as DefenderResponse;
}

/** Light health probe so the UI can show a connection indicator. */
export async function pingBackend(
  options: {
    fetcher?: FetchLike;
    backendOverride?: string;
    timeoutMs?: number;
  } = {},
): Promise<boolean> {
  const fetcher = options.fetcher ?? fetch;
  const url = `${options.backendOverride ?? backendUrl()}/healthz`;
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), options.timeoutMs ?? 1500);
  try {
    const resp = await fetcher(url, { signal: controller.signal });
    return resp.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}
