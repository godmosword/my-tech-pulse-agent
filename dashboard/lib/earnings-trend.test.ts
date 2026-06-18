import { describe, expect, it, vi } from "vitest";

// earnings-firestore is server-only; stub the guard so the pure parser is importable in tests.
vi.mock("server-only", () => ({}));

import { parseEarningsTrend } from "./earnings-firestore";

describe("parseEarningsTrend", () => {
  it("parses a well-formed trend payload", () => {
    const parsed = parseEarningsTrend({
      quarters_covered: 4,
      trends: [
        {
          metric: "revenue",
          label_zh: "營收",
          direction: "擴張",
          yoy_pct: 0.25,
          qoq_pct: 0.05,
          points: [
            { fiscal_year: 2025, fiscal_period: "Q1", period_end: "2025-03-31", value: 10 },
            { fiscal_year: 2025, fiscal_period: "Q2", value: 12 },
          ],
        },
      ],
    });
    expect(parsed).not.toBeNull();
    expect(parsed!.quarters_covered).toBe(4);
    expect(parsed!.trends).toHaveLength(1);
    expect(parsed!.trends[0].points).toHaveLength(2);
    expect(parsed!.trends[0].yoy_pct).toBe(0.25);
  });

  it("returns null for absent / empty / malformed input", () => {
    expect(parseEarningsTrend(null)).toBeNull();
    expect(parseEarningsTrend(undefined)).toBeNull();
    expect(parseEarningsTrend({})).toBeNull();
    expect(parseEarningsTrend({ trends: [] })).toBeNull();
    expect(parseEarningsTrend({ trends: [{ label_zh: "no metric" }] })).toBeNull();
  });

  it("coerces bad point fields to null without dropping the metric", () => {
    const parsed = parseEarningsTrend({
      trends: [
        {
          metric: "eps",
          points: [{ fiscal_year: "2025", fiscal_period: 2, value: "x" }],
        },
      ],
    });
    expect(parsed).not.toBeNull();
    const p = parsed!.trends[0].points[0];
    expect(p.fiscal_year).toBeNull();
    expect(p.value).toBeNull();
    expect(parsed!.trends[0].direction).toBe("資料不足");
  });
});
