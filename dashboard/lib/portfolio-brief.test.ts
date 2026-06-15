import { describe, expect, it } from "vitest";

import { impactPosture, rankItemsByImpact } from "./portfolio-brief";
import type { RenderableItem } from "./types";

function item(id: string, score: number | null): RenderableItem {
  return {
    id,
    title: id,
    zh_title: "",
    summary: "",
    zh_summary: "",
    zh_body: "",
    source_url: "",
    source_name: "",
    entity: "",
    category: "",
    kind: "instant_summary",
    score: 0,
    score_status: "ok",
    hook: "",
    tickers: [],
    what_happened: "",
    why_it_matters: "",
    takeaway: null,
    portfolio_impact:
      score === null
        ? null
        : {
            score,
            affected_positions: [],
            exposure_basis: "cost",
            rationale_zh: "",
          },
    published_at_iso: null,
    delivered_at_iso: null,
    themes: [],
  };
}

describe("impactPosture", () => {
  it("maps impact bands to posture (mirrors posture.py)", () => {
    expect(impactPosture(0.05)).toBe("no_action");
    expect(impactPosture(0.25)).toBe("monitor");
    expect(impactPosture(0.6)).toBe("review");
  });
});

describe("rankItemsByImpact", () => {
  it("drops zero-impact items and sorts by impact desc", () => {
    const items = [item("a", 0.1), item("b", 0.6), item("c", 0), item("d", null)];
    const ranked = rankItemsByImpact(items);
    expect(ranked.map((i) => i.id)).toEqual(["b", "a"]);
  });

  it("respects the limit", () => {
    const items = [item("a", 0.5), item("b", 0.4), item("c", 0.3)];
    expect(rankItemsByImpact(items, 2)).toHaveLength(2);
  });
});
