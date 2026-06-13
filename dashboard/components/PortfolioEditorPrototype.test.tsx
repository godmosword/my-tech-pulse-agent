/** @vitest-environment jsdom */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PortfolioEditorPrototype } from "./PortfolioEditorPrototype";

afterEach(() => {
  cleanup();
});

describe("PortfolioEditorPrototype", () => {
  it("exposes the editor table with an accessible name and column headers", () => {
    render(
      <PortfolioEditorPrototype
        initialPositions={[{ ticker: "NVDA", shares: 10, avg_cost: 100 }]}
        asOf="2026-05-18"
        baseCurrency="USD"
      />,
    );

    // Table is named via aria-labelledby -> the section heading.
    const table = screen.getByRole("table", { name: "持倉編輯（原型）" });
    expect(table).toBeInTheDocument();

    // Column headers are programmatically exposed (scope="col").
    const headers = screen.getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "代號",
      "股數",
      "成本",
      "操作",
    ]);
  });
});
