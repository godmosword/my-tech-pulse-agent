import { describe, expect, it } from "vitest";

import { tagItemPortfolioRelevance } from "./portfolio-relevance";

describe("tagItemPortfolioRelevance", () => {
  const holdings = new Set(["NVDA", "MU"]);
  const watchlist = new Set(["AMD", "TSM"]);

  it("returns holding when ticker matches portfolio", () => {
    const result = tagItemPortfolioRelevance(["nvda", "INTC"], holdings, watchlist);
    expect(result.relevance).toBe("holding");
    expect(result.matched).toEqual(["NVDA"]);
  });

  it("returns watchlist when only watchlist tickers match", () => {
    const result = tagItemPortfolioRelevance(["AMD"], holdings, watchlist);
    expect(result.relevance).toBe("watchlist");
    expect(result.matched).toEqual(["AMD"]);
  });

  it("returns none when no tickers match", () => {
    const result = tagItemPortfolioRelevance(["AAPL"], holdings, watchlist);
    expect(result.relevance).toBe("none");
    expect(result.matched).toEqual([]);
  });

  it("prefers holding over watchlist when both match", () => {
    const both = new Set(["NVDA", "AMD"]);
    const result = tagItemPortfolioRelevance(["AMD", "NVDA"], both, watchlist);
    expect(result.relevance).toBe("holding");
    expect(result.matched).toContain("NVDA");
    expect(result.matched).toContain("AMD");
  });

  it("handles empty or missing tickers", () => {
    expect(tagItemPortfolioRelevance(undefined, holdings, watchlist)).toEqual({
      relevance: "none",
      matched: [],
    });
    expect(tagItemPortfolioRelevance([], holdings, watchlist)).toEqual({
      relevance: "none",
      matched: [],
    });
  });
});
