import { describe, expect, it } from "vitest";

import type { RenderableItem } from "./types";
import {
  bilingualEnglishSummary,
  bilingualEnglishTitle,
  shouldShowBilingualCompare,
} from "./zh-content";

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

describe("bilingual compare helpers", () => {
  it("returns English title when it differs from the Chinese headline", () => {
    expect(bilingualEnglishTitle(item())).toBe(
      "Nvidia launches new chip architecture",
    );
  });

  it("returns null English title when it matches the displayed headline", () => {
    expect(
      bilingualEnglishTitle(
        item({ zh_title: "", zh_summary: "", title: "Only English title" }),
      ),
    ).toBeNull();
  });

  it("returns English summary without requiring zh_body", () => {
    expect(bilingualEnglishSummary(item({ zh_body: "" }))).toBe(
      "Nvidia announced a new GPU architecture for data centers.",
    );
  });

  it("shows compare when zh_summary + summary exist and zh_body is empty", () => {
    expect(shouldShowBilingualCompare(item({ zh_body: "" }))).toBe(true);
  });

  it("shows compare when only zh_title exists alongside English", () => {
    expect(
      shouldShowBilingualCompare(
        item({ zh_summary: "", zh_body: "" }),
      ),
    ).toBe(true);
  });

  it("hides compare when there is only English and no Chinese", () => {
    expect(
      shouldShowBilingualCompare(
        item({
          zh_title: "",
          zh_summary: "",
          zh_body: "",
          title: "Only English title",
          summary: "Only English summary.",
        }),
      ),
    ).toBe(false);
  });
});
