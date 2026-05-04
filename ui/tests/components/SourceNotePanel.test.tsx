import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { SourceNotePanel } from "../../src/components/SourceNotePanel";
import type { Citation } from "../../src/api/types";

const note = "CC: thick painful nails. HPI: weeks of symptoms.";

describe("SourceNotePanel", () => {
  it("renders the note unchanged when no highlight is provided", () => {
    render(<SourceNotePanel noteText={note} highlight={null} />);
    expect(screen.getByTestId("source-note")).toHaveTextContent(
      "CC: thick painful nails",
    );
    expect(screen.queryByTestId("source-note-highlight")).toBeNull();
  });

  it("highlights the cited span for an encounter citation", () => {
    const citation: Citation = {
      source_type: "encounter",
      span: { text: "thick painful nails", start_char: 4, end_char: 23 },
      policy_id: null,
      rationale: "x",
    };
    render(<SourceNotePanel noteText={note} highlight={citation} />);
    const mark = screen.getByTestId("source-note-highlight");
    expect(mark).toHaveTextContent("thick painful nails");
  });

  it("does not highlight when the citation is a policy citation", () => {
    const citation: Citation = {
      source_type: "policy",
      span: { text: "x", start_char: 0, end_char: 1 },
      policy_id: "p",
      rationale: "x",
    };
    render(<SourceNotePanel noteText={note} highlight={citation} />);
    expect(screen.queryByTestId("source-note-highlight")).toBeNull();
  });
});
