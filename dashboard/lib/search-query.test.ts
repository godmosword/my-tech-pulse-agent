import { describe, expect, it } from "vitest";

import {
  normalizeSearchQuery,
  SearchQuerySchema,
  titlePrefixBounds,
} from "./search-query";

describe("search-query", () => {
  it("validates q with zod", () => {
    expect(SearchQuerySchema.safeParse({ q: " NVDA " }).success).toBe(true);
    expect(SearchQuerySchema.safeParse({ q: "" }).success).toBe(false);
    expect(SearchQuerySchema.safeParse({ q: "x".repeat(81) }).success).toBe(false);
  });

  it("normalizes ticker-like input to uppercase", () => {
    expect(normalizeSearchQuery("nvda")).toEqual({
      q: "nvda",
      ticker: "NVDA",
      isTickerLike: true,
    });
  });

  it("keeps non-ticker keywords as title search only", () => {
    expect(normalizeSearchQuery("AI chip")).toEqual({
      q: "AI chip",
      ticker: null,
      isTickerLike: false,
    });
  });

  it("builds ascii title prefix bounds", () => {
    const bounds = titlePrefixBounds("nvidia");
    expect(bounds).toContain("nvidia");
    expect(bounds).toContain("Nvidia");
    expect(bounds).toContain("NVIDIA");
  });
});
