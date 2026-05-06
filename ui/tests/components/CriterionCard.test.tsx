import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { CriterionCard } from "../../src/components/CriterionCard";
import type { CriterionScore } from "../../src/api/types";

const passingScore: CriterionScore = {
  verdict: "PASS",
  confidence: 0.91,
  evidence: [
    {
      source_type: "encounter",
      span: { text: "thick painful nails", start_char: 0, end_char: 19 },
      policy_id: null,
      rationale: "CC names a problem distinct from the procedure indication.",
    },
  ],
};

describe("CriterionCard", () => {
  it("renders the criterion label, verdict, and confidence", () => {
    render(
      <CriterionCard
        name="distinct_cc"
        score={passingScore}
        onCitationClick={() => undefined}
      />,
    );
    expect(screen.getByText("Distinct CC")).toBeInTheDocument();
    expect(screen.getByText("PASS")).toBeInTheDocument();
    expect(screen.getByText(/confidence 91%/)).toBeInTheDocument();
  });

  it("invokes onCitationClick with the cited Citation", () => {
    const onClick = vi.fn();
    render(
      <CriterionCard
        name="distinct_cc"
        score={passingScore}
        onCitationClick={onClick}
      />,
    );
    fireEvent.click(screen.getByText("encounter"));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick.mock.calls[0][0]).toEqual(passingScore.evidence[0]);
  });
});
