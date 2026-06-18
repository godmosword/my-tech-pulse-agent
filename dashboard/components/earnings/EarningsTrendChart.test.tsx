/** @vitest-environment jsdom */

import { describe, expect, it } from "vitest";

import type { MetricTrendRow } from "@/lib/earnings-firestore";

import { metricChartData } from "./EarningsTrendChart";

function metric(over: Partial<MetricTrendRow> = {}): MetricTrendRow {
  return {
    metric: "revenue",
    label_zh: "營收",
    points: [],
    yoy_pct: null,
    qoq_pct: null,
    direction: "資料不足",
    ...over,
  };
}

describe("metricChartData", () => {
  it("keeps numeric points oldest→newest with a fiscal-period label", () => {
    const data = metricChartData(
      metric({
        points: [
          { fiscal_year: 2025, fiscal_period: "Q1", period_end: null, value: 10 },
          { fiscal_year: 2025, fiscal_period: "Q2", period_end: null, value: 12 },
        ],
      }),
    );
    expect(data).toEqual([
      { name: "2025 Q1", value: 10 },
      { name: "2025 Q2", value: 12 },
    ]);
  });

  it("drops points with null values", () => {
    const data = metricChartData(
      metric({
        points: [
          { fiscal_year: 2025, fiscal_period: "Q1", period_end: null, value: null },
          { fiscal_year: 2025, fiscal_period: "Q2", period_end: null, value: 5 },
        ],
      }),
    );
    expect(data).toEqual([{ name: "2025 Q2", value: 5 }]);
  });
});
