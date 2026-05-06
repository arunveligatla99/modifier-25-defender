import { describe, expect, it, vi } from "vitest";

import { analyzeEncounter } from "../../src/api/client";
import type { DefenderRequest, DefenderResponse } from "../../src/api/types";

const baseRequest: DefenderRequest = {
  encounter_id: "ui-test",
  note_text: "CC: thick painful nails.",
  em_code: "99213",
  procedure_code: "11721",
  modifier_25_attached: true,
  site: "L",
};

const baseResponse: DefenderResponse = {
  encounter_id: "ui-test",
  parsed: {
    cc: [],
    hpi: [],
    exam_findings: [],
    mdm: [],
    procedure_note: [],
    ambiguous_segments: [],
  },
  assessment: null,
  remediations: [],
  compliance_status: "BLOCKED",
  blocked_reasons: ["criterion=independent_mdm: NLI 0.42 below 0.75"],
  trace_id: "lf_t_local_x",
};

describe("analyzeEncounter", () => {
  it("POSTs to /analyze and returns the parsed response", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => baseResponse,
    } as unknown as Response);
    const result = await analyzeEncounter(baseRequest, {
      fetcher: fetcher as unknown as typeof fetch,
      backendOverride: "http://test",
    });
    expect(fetcher).toHaveBeenCalledWith(
      "http://test/analyze",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toEqual(baseResponse);
  });

  it("throws an AnalyzeError on non-ok response", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ error: "phi_detected", reason: "DOB present" }),
    } as unknown as Response);
    await expect(
      analyzeEncounter(baseRequest, {
        fetcher: fetcher as unknown as typeof fetch,
        backendOverride: "http://test",
      }),
    ).rejects.toMatchObject({
      status: 422,
      error: "phi_detected",
      reason: "DOB present",
    });
  });
});
