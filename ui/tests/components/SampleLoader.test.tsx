import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SampleLoader } from "../../src/components/SampleLoader";

describe("SampleLoader", () => {
  it("renders three sample buttons (PASS, WEAK, FAIL)", () => {
    render(<SampleLoader onLoad={() => {}} activeId={null} />);
    expect(screen.getByTestId("sample-load-pass")).toBeInTheDocument();
    expect(screen.getByTestId("sample-load-weak")).toBeInTheDocument();
    expect(screen.getByTestId("sample-load-fail")).toBeInTheDocument();
  });

  it("calls onLoad with the sample for the clicked button", () => {
    const onLoad = vi.fn();
    render(<SampleLoader onLoad={onLoad} activeId={null} />);
    fireEvent.click(screen.getByTestId("sample-load-fail"));
    expect(onLoad).toHaveBeenCalledTimes(1);
    expect(onLoad.mock.calls[0][0].expectedVerdict).toBe("FAIL");
  });

  it("disables buttons when disabled is true", () => {
    render(<SampleLoader onLoad={() => {}} activeId={null} disabled />);
    expect(screen.getByTestId("sample-load-pass")).toBeDisabled();
  });
});
