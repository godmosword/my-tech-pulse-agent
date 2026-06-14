import { describe, expect, it } from "vitest";

import { QUERY_TOKEN_LIMIT, tokenizeQuery, tokenMatchScore } from "./search-tokens";

// Mirror of tests/test_search_tokens.py — keep the two in lock-step.
describe("tokenizeQuery", () => {
  it("lowercases latin words and drops single chars", () => {
    expect(tokenizeQuery("Nvidia AI a")).toEqual(["ai", "nvidia"]);
  });

  it("splits CJK into bigrams", () => {
    expect(tokenizeQuery("輝達財報")).toEqual(["財報", "達財", "輝達"].sort());
  });

  it("keeps a single CJK char", () => {
    expect(tokenizeQuery("台")).toEqual(["台"]);
  });

  it("returns sorted, deduped tokens", () => {
    expect(tokenizeQuery("beta alpha BETA")).toEqual(["alpha", "beta"]);
  });

  it("trims and handles empty input", () => {
    expect(tokenizeQuery("   ")).toEqual([]);
    expect(tokenizeQuery("")).toEqual([]);
  });

  it("caps at the Firestore array-contains-any limit", () => {
    const long = Array.from({ length: 50 }, (_, i) => `w${i}`).join(" ");
    expect(tokenizeQuery(long)).toHaveLength(QUERY_TOKEN_LIMIT);
  });
});

describe("tokenMatchScore", () => {
  it("counts overlapping tokens", () => {
    expect(tokenMatchScore(["nvidia", "ai"], ["why", "nvidia", "ai", "beat"])).toBe(2);
  });

  it("is zero with no overlap or empty input", () => {
    expect(tokenMatchScore(["x"], ["y"])).toBe(0);
    expect(tokenMatchScore([], ["y"])).toBe(0);
    expect(tokenMatchScore(["x"], [])).toBe(0);
  });
});
