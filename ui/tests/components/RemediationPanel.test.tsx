import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { RemediationPanel } from "../../src/components/RemediationPanel";
import type { RemediationSuggestion } from "../../src/api/types";

const SUGG: RemediationSuggestion = {
  criterion: "independent_mdm",
  suggested_addition: "Document a concrete management plan today.",
  motivation: [
    {
      source_type: "policy",
      span: { text: "policy basis text", start_char: 0, end_char: 17 },
      policy_id: "test-policy|abc",
      rationale: "Policy requires concrete plan.",
    },
  ],
};

describe("RemediationPanel", () => {
  it("returns null when there are no suggestions", () => {
    const { container } = render(<RemediationPanel suggestions={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the suggestion text and the criterion label", () => {
    render(<RemediationPanel suggestions={[SUGG]} />);
    expect(screen.getByTestId("remediation-panel")).toBeInTheDocument();
    expect(screen.getByText(/Independent MDM/i)).toBeInTheDocument();
    expect(
      screen.getByText("Document a concrete management plan today."),
    ).toBeInTheDocument();
    // Policy basis is in a <details>; the summary is visible.
    expect(screen.getByText(/Policy basis \(1\)/i)).toBeInTheDocument();
  });
});
