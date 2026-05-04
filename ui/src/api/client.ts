/**
 * Typed POST /analyze client.
 *
 * Production deployments may target a different backend host; configure via
 * the VITE_BACKEND_URL environment variable (see infra/docker-compose.yaml).
 * The fetcher is injectable for testing.
 */

import type { DefenderRequest, DefenderResponse } from "./types";

export interface AnalyzeError {
  status: number;
  error: string;
  reason?: string;
  details?: unknown;
}

export type FetchLike = typeof fetch;

const DEFAULT_BACKEND_URL = "http://localhost:8000";

function backendUrl(): string {
  const env =
    typeof import.meta !== "undefined" ? import.meta.env : undefined;
  return (env && (env.VITE_BACKEND_URL as string | undefined)) || DEFAULT_BACKEND_URL;
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
