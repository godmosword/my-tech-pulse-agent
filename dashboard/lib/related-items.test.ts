import { describe, expect, it } from "vitest";

import type { RenderableItem } from "./types";
import { pickRelatedItems } from "./related-items";

function item(overrides: Partial<RenderableItem> = {}): RenderableItem {
  return {
    id: "item-1",
    title: "Nvidia launches new chip architecture",
    zh_title: "輝達發表新一代資料中心晶片架構",
    summary: "Nvidia announced a new GPU architecture for data centers.",
    zh_summary: "輝達宣布新一代資料中心 GPU 架構。",
    zh_body: "",
    source_url: "",
    source_name: "Source",
    entity: "Nvidia",
    category: "ai",
    kind: "instant_summary",
    score: 7,
    score_status: "ok",
    hook: "",
    tickers: ["NVDA"],
    what_happened: "",
    why_it_matters: "",
    takeaway: null,
    portfolio_impact: null,
    published_at_iso: null,
    delivered_at_iso: "2026-08-16T10:00:00.000Z",
    themes: [],
    ...overrides,
  };
}

describe("pickRelatedItems", () => {
  it("excludes the current item", () => {
    const current = item({ id: "current" });
    const candidates = [current, item({ id: "other", category: "ai" })];
    expect(pickRelatedItems(current, candidates)).toEqual([candidates[1]]);
  });

  it("ranks ticker overlap above category-only matches", () => {
    const current = item({ id: "current", category: "ai", tickers: ["NVDA"] });
    const categoryOnly = item({
      id: "category-only",
      category: "ai",
      tickers: [],
    });
    const tickerMatch = item({
      id: "ticker-match",
      category: "markets",
      tickers: ["nvda"],
    });

    expect(
      pickRelatedItems(current, [categoryOnly, tickerMatch], 2),
    ).toEqual([tickerMatch, categoryOnly]);
  });

  it("includes same-category items and excludes unrelated ones", () => {
    const current = item({ id: "current", category: "ai", tickers: [] });
    const sameCategory = item({
      id: "same-category",
      category: "ai",
      tickers: [],
    });
    const unrelated = item({
      id: "unrelated",
      category: "markets",
      tickers: ["AAPL"],
    });

    expect(pickRelatedItems(current, [sameCategory, unrelated])).toEqual([
      sameCategory,
    ]);
  });

  it("does not match empty categories unless tickers overlap", () => {
    const current = item({ id: "current", category: "", tickers: ["NVDA"] });
    const emptyCategory = item({
      id: "empty-category",
      category: "",
      tickers: [],
    });
    const tickerMatch = item({
      id: "ticker-match",
      category: "",
      tickers: ["NVDA"],
    });

    expect(
      pickRelatedItems(current, [emptyCategory, tickerMatch], 2),
    ).toEqual([tickerMatch]);
  });

  it("caps results at the provided limit", () => {
    const current = item({ id: "current", category: "ai", tickers: [] });
    const candidates = [
      item({ id: "one", category: "ai", tickers: [] }),
      item({ id: "two", category: "ai", tickers: [] }),
      item({ id: "three", category: "ai", tickers: [] }),
    ];

    expect(pickRelatedItems(current, candidates, 2)).toHaveLength(2);
    expect(pickRelatedItems(current, candidates, 2).map((row) => row.id)).toEqual(
      ["one", "two"],
    );
  });

  it("matches tickers case-insensitively", () => {
    const current = item({ id: "current", category: "", tickers: ["nvda"] });
    const candidate = item({
      id: "match",
      category: "markets",
      tickers: ["NVDA"],
    });

    expect(pickRelatedItems(current, [candidate])).toEqual([candidate]);
  });
});
