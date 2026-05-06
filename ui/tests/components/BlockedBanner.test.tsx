import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { BlockedBanner } from "../../src/components/BlockedBanner";

describe("BlockedBanner", () => {
  it("renders the BLOCKED title and reason items", () => {
    render(
      <BlockedBanner
        reasons={[
          "criterion=independent_mdm: NLI 0.42 below 0.75",
          "remediation=distinct_cc: NLI 0.55 below 0.75",
        ]}
      />,
    );
    expect(screen.getByText(/BLOCKED by Compliance Guard/)).toBeInTheDocument();
    expect(
      screen.getByText(/criterion=independent_mdm: NLI 0.42 below 0.75/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/remediation=distinct_cc: NLI 0.55 below 0.75/),
    ).toBeInTheDocument();
  });

  it("uses an alert role for screen readers", () => {
    render(<BlockedBanner reasons={["x"]} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
