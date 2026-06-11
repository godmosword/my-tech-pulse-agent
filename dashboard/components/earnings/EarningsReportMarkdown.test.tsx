/** @vitest-environment jsdom */

import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EarningsReportMarkdown } from "./EarningsReportMarkdown";
import { EarningsReportEmpty } from "./EarningsReportEmpty";

afterEach(() => {
  cleanup();
});

const SAMPLE = `## Scorecard

重點摘要

### 營收

| 指標 | 數值 |
| --- | ---: |
| YoY | 12% |

## 結論

維持中性看法。
`;

describe("EarningsReportMarkdown", () => {
  it("renders headings and table with data-table class", () => {
    render(<EarningsReportMarkdown content={SAMPLE} />);

    expect(screen.getByRole("heading", { level: 2, name: "Scorecard" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 3, name: "營收" })).toBeTruthy();
    const table = screen.getByRole("table");
    expect(table.className).toContain("data-table");
    expect(screen.getByText("YoY")).toBeTruthy();
  });

  it("renders chapter navigation", () => {
    render(<EarningsReportMarkdown content={SAMPLE} />);
    expect(screen.getByRole("navigation", { name: "章節目錄" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "跳至章節" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Scorecard" })).toBeTruthy();
  });
});

describe("EarningsReportEmpty", () => {
  it("shows friendly empty state without storage jargon", () => {
    render(<EarningsReportEmpty ticker="NVDA" />);
    expect(screen.getByText("深度報告尚未就緒")).toBeTruthy();
    expect(screen.queryByText(/Firestore/i)).toBeNull();
    expect(screen.getByRole("link", { name: "NVDA 財報總覽" })).toHaveAttribute(
      "href",
      "/earnings/NVDA",
    );
  });
});
