import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { OverallVerdict } from "../../src/components/OverallVerdict";
import type { CriteriaMap } from "../../src/api/types";

const SCORE = (v: "PASS" | "WEAK" | "FAIL") => ({
  verdict: v,
  confidence: 0.9,
  evidence: [
    {
      source_type: "encounter" as const,
      span: { text: "x", start_char: 0, end_char: 1 },
      policy_id: null,
      rationale: "r",
    },
  ],
});

const CRITERIA: CriteriaMap = {
  distinct_cc: SCORE("PASS"),
  separate_exam: SCORE("WEAK"),
  independent_mdm: SCORE("PASS"),
  site_specificity: SCORE("PASS"),
};

describe("OverallVerdict", () => {
  it("renders the verdict pill and per-criterion roll-up", () => {
    render(<OverallVerdict verdict="WEAK" criteria={CRITERIA} />);
    expect(screen.getByLabelText("overall WEAK")).toBeInTheDocument();
    // Roll-up cells expose the four short codes.
    expect(screen.getByText("CC")).toBeInTheDocument();
    expect(screen.getByText("Exam")).toBeInTheDocument();
    expect(screen.getByText("MDM")).toBeInTheDocument();
    expect(screen.getByText("Site")).toBeInTheDocument();
  });

  it("uses the FAIL blurb for FAIL verdicts", () => {
    render(
      <OverallVerdict
        verdict="FAIL"
        criteria={{
          ...CRITERIA,
          distinct_cc: SCORE("FAIL"),
        }}
      />,
    );
    expect(
      screen.getByText(/does not support modifier 25/i),
    ).toBeInTheDocument();
  });
});
