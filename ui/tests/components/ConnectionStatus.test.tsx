import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ConnectionStatus } from "../../src/components/ConnectionStatus";

describe("ConnectionStatus", () => {
  it("shows 'Live backend' when state is live", () => {
    render(<ConnectionStatus state="live" url="http://x" />);
    expect(screen.getByText(/Live backend/)).toBeInTheDocument();
  });

  it("shows 'Demo mode' when state is demo", () => {
    render(<ConnectionStatus state="demo" url="http://x" />);
    expect(screen.getByText(/Demo mode/)).toBeInTheDocument();
  });

  it("shows checking state with pulse class", () => {
    render(<ConnectionStatus state="checking" url="http://x" />);
    expect(screen.getByText(/Checking backend/)).toBeInTheDocument();
  });
});
