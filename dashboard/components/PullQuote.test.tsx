/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PullQuote } from "./PullQuote";

afterEach(() => {
  cleanup();
});

describe("PullQuote", () => {
  it("renders the quote text", () => {
    render(<PullQuote>關鍵在於資本配置。</PullQuote>);
    expect(screen.getByText("關鍵在於資本配置。")).toBeInTheDocument();
  });

  it("renders an optional citation", () => {
    render(<PullQuote cite="NVDA · FY25 Q3">摘錄</PullQuote>);
    expect(screen.getByText("NVDA · FY25 Q3")).toBeInTheDocument();
  });

  it("omits the citation when not provided", () => {
    const { container } = render(<PullQuote>無出處</PullQuote>);
    expect(container.querySelector("figcaption")).toBeNull();
  });
});
