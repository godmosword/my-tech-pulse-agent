/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Sparkline } from "./Sparkline";

afterEach(() => {
  cleanup();
});

describe("Sparkline", () => {
  it("renders an accessible path for two or more points", () => {
    render(<Sparkline values={[1, 2, 3]} ariaLabel="EPS 走勢" />);
    const svg = screen.getByRole("img", { name: "EPS 走勢" });
    const path = svg.querySelector("path");
    expect(path).not.toBeNull();
    expect(path?.getAttribute("d")).toMatch(/^M/);
  });

  it("renders an end dot by default and hides it when disabled", () => {
    const { container, rerender } = render(
      <Sparkline values={[1, 5, 2]} ariaLabel="趨勢" />,
    );
    expect(container.querySelector("circle")).not.toBeNull();

    rerender(<Sparkline values={[1, 5, 2]} ariaLabel="趨勢" showEndDot={false} />);
    expect(container.querySelector("circle")).toBeNull();
  });

  it("renders nothing below two finite points", () => {
    const { container } = render(
      <Sparkline values={[NaN, 3]} ariaLabel="不足" />,
    );
    expect(container.firstChild).toBeNull();
  });
});
