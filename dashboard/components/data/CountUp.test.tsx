/** @vitest-environment jsdom */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CountUp } from "./CountUp";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubReducedMotion(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

describe("CountUp", () => {
  it("renders the final value immediately under reduced motion", () => {
    stubReducedMotion(true);
    render(<CountUp value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("settles on the final formatted value after animating", async () => {
    stubReducedMotion(false);
    render(<CountUp value={3.5} format={(n) => n.toFixed(1)} />);
    await waitFor(() => {
      expect(screen.getByText("3.5")).toBeInTheDocument();
    });
  });
});
