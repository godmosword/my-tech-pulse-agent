/** @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MetricHint } from "./MetricHint";

afterEach(cleanup);

describe("MetricHint", () => {
  it("toggles an accessible popover on click (not hover-only)", () => {
    render(<MetricHint metric="ic" />);
    const button = screen.getByRole("button", { name: /IC.*說明/ });
    expect(button).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    // The plain-language explanation is shown, including a high/low cue.
    expect(screen.getByText(/越接近 \+1 越有預測力/)).toBeInTheDocument();

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  it("closes on Escape", () => {
    render(<MetricHint metric="hit_rate" />);
    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(button).toHaveAttribute("aria-expanded", "false");
  });
});
