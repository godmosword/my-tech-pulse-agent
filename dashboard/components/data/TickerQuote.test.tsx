/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TickerQuote } from "./TickerQuote";

afterEach(() => {
  cleanup();
});

describe("TickerQuote", () => {
  it("links the ticker chip to /earnings/[ticker]", () => {
    render(<TickerQuote ticker="NVDA" />);
    const link = screen.getByRole("link", { name: /NVDA/ });
    expect(link.getAttribute("href")).toBe("/earnings/NVDA");
  });

  it("still shows price and change when a quote is provided", () => {
    render(
      <TickerQuote
        ticker="NVDA"
        quote={{ price: 120.5, changePct: 1.2 }}
      />,
    );
    expect(screen.getByText("$120.50")).toBeInTheDocument();
    expect(screen.getByText("+1.2%")).toBeInTheDocument();
  });
});
