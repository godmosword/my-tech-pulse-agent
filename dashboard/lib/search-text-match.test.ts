import { describe, expect, it } from "vitest";

import type { RenderableItem } from "./types";
import {
  renderableMatchesQuery,
  tokensFromRenderable,
} from "./search-text-match";

function item(overrides: Partial<RenderableItem> = {}): RenderableItem {
  return {
    id: "item-1",
    title: "",
    zh_title: "",
    summary: "",
    zh_summary: "",
    zh_body: "",
    source_url: "",
    source_name: "",
    entity: "",
    category: "ai",
    kind: "instant_summary",
    score: 1,
    score_status: "ok",
    hook: "",
    tickers: [],
    what_happened: "",
    why_it_matters: "",
    takeaway: null,
    published_at_iso: null,
    delivered_at_iso: "2026-05-18T10:00:00.000Z",
    themes: [],
    ...overrides,
  };
}

describe("tokensFromRenderable", () => {
  it("includes tokens from title, summary, and tickers", () => {
    const tokens = tokensFromRenderable(
      item({
        title: "Why Nvidia earnings beat",
        tickers: ["NVDA"],
      }),
    );
    expect(tokens).toContain("nvidia");
    expect(tokens).toContain("nvda");
  });
});

describe("renderableMatchesQuery", () => {
  it("matches mid-title keyword via token overlap", () => {
    expect(
      renderableMatchesQuery(
        item({ title: "Why Nvidia earnings beat", tickers: ["NVDA"] }),
        "nvidia",
      ),
    ).toBe(true);
  });

  it("matches CJK substring in zh_title without stored search_tokens", () => {
    expect(
      renderableMatchesQuery(item({ zh_title: "輝達財報亮眼" }), "財報"),
    ).toBe(true);
  });

  it("matches keyword in summary when title has no hit", () => {
    expect(
      renderableMatchesQuery(
        item({ title: "Market update", summary: "TSMC capacity expansion" }),
        "tsmc",
      ),
    ).toBe(true);
  });

  it("matches ticker symbol exactly", () => {
    expect(
      renderableMatchesQuery(item({ title: "Chip news", tickers: ["AMD"] }), "AMD"),
    ).toBe(true);
  });

  it("uses stored search_tokens when provided", () => {
    expect(
      renderableMatchesQuery(
        item({ title: "Unrelated headline" }),
        "nvidia",
        ["nvidia", "ai"],
      ),
    ).toBe(true);
  });

  it("returns false for empty or non-matching query", () => {
    expect(renderableMatchesQuery(item({ title: "Hello" }), "")).toBe(false);
    expect(renderableMatchesQuery(item({ title: "Hello" }), "zzzz")).toBe(false);
  });
});
