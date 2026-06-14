/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PageSkeleton } from "./PageSkeleton";

afterEach(() => {
  cleanup();
});

describe("PageSkeleton", () => {
  it("announces a busy loading status to assistive tech", () => {
    render(<PageSkeleton />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "載入中");
    expect(screen.getByText("載入中…")).toBeInTheDocument();
  });
});
