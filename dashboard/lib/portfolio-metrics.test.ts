import { describe, expect, it } from "vitest";

import {
  allocationDrift,
  classifyTier,
  themeExposure,
  valuePositions,
} from "./portfolio-metrics";

describe("classifyTier", () => {
  const holdings = new Set(["NVDA", "MU"]);
  const watchlist = new Set(["AMD", "TSM"]);

  it("classifies holding, watchlist, and other", () => {
    expect(classifyTier("nvda", holdings, watchlist)).toBe("holding");
    expect(classifyTier("AMD", holdings, watchlist)).toBe("watchlist");
    expect(classifyTier("ZZZ", holdings, watchlist)).toBe("other");
  });
});

describe("themeExposure", () => {
  it("weights sum to approximately 100", () => {
    const valued = [
      {
        ticker: "NVDA",
        shares: 100,
        avgCost: 100,
        price: 200,
        marketValue: 20000,
        usedCostBasis: false,
      },
      {
        ticker: "MU",
        shares: 50,
        avgCost: 80,
        price: 100,
        marketValue: 5000,
        usedCostBasis: false,
      },
    ];
    const exposure = themeExposure(valued, (t) =>
      t === "NVDA" ? "ai_silicon" : "memory",
    );
    const sum = exposure.reduce((s, r) => s + r.weightPct, 0);
    expect(sum).toBeGreaterThan(99);
    expect(sum).toBeLessThanOrEqual(100.01);
  });
});

describe("allocationDrift", () => {
  it("positive drift when over target", () => {
    const exposure = [{ theme: "ai_silicon", marketValue: 8000, weightPct: 80 }];
    const drift = allocationDrift(exposure, { ai_silicon: 0.4 });
    const row = drift.find((d) => d.theme === "ai_silicon");
    expect(row?.driftPct).toBeGreaterThan(0);
  });

  it("negative drift when under target", () => {
    const exposure = [{ theme: "memory", marketValue: 1000, weightPct: 10 }];
    const drift = allocationDrift(exposure, { memory: 0.15 });
    const row = drift.find((d) => d.theme === "memory");
    expect(row?.driftPct).toBeLessThan(0);
  });
});

describe("valuePositions", () => {
  it("falls back to cost basis when price missing", () => {
    const prices = new Map<string, number | null>();
    const { rows, priced } = valuePositions(
      [{ ticker: "NVDA", shares: 10, avgCost: 100 }],
      prices,
    );
    expect(priced).toBe(false);
    expect(rows[0].marketValue).toBe(1000);
    expect(rows[0].usedCostBasis).toBe(true);
  });
});
