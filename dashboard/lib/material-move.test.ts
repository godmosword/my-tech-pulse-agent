import { describe, expect, it } from "vitest";

import type { BriefItem } from "./invest-brief";
import { materialMoveFromBrief, materialMoveFromItem } from "./material-move";
import type { RenderableItem } from "./types";

const BRIEF: BriefItem = {
  id: "b1",
  title: "NVDA 供應鏈警訊",
  impact_score: 0.62,
  posture: "review",
  label_zh: "需要複核",
  reason_zh: "資料中心需求轉弱",
  falsification_zh: "下季營收回升",
  next_check: "2026-07-01",
  affected_tickers: ["NVDA", "AVGO"],
  market_flags: ["near_52w_high"],
};

function renderable(over: Partial<RenderableItem> = {}): RenderableItem {
  return {
    id: "i1",
    title: "Item",
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
    portfolio_impact: null,
    published_at_iso: null,
    delivered_at_iso: null,
    themes: [],
    ...over,
  };
}

describe("materialMoveFromBrief", () => {
  it("maps every brief field into the shared view without dropping detail", () => {
    const v = materialMoveFromBrief(BRIEF);
    expect(v.title).toBe("NVDA 供應鏈警訊");
    expect(v.href).toBe("/item/b1");
    expect(v.postureLabel).toBe("需要複核");
    expect(v.postureClass).toMatch(/^text-/);
    expect(v.reason).toBe("資料中心需求轉弱");
    expect(v.affectedTickers).toEqual(["NVDA", "AVGO"]);
    expect(v.marketFlags).toEqual(["near_52w_high"]);
    expect(v.falsification).toBe("下季營收回升");
    expect(v.nextCheck).toBe("2026-07-01");
  });

  it("leaves falsification/nextCheck undefined when empty", () => {
    const v = materialMoveFromBrief({
      ...BRIEF,
      falsification_zh: "",
      next_check: "",
    });
    expect(v.falsification).toBeUndefined();
    expect(v.nextCheck).toBeUndefined();
  });
});

describe("materialMoveFromItem", () => {
  it("maps a live item's portfolio_impact into the same shape", () => {
    const v = materialMoveFromItem(
      renderable({
        id: "x9",
        title: "AVGO 訂單",
        portfolio_impact: {
          score: 0.5,
          affected_positions: [{ ticker: "AVGO", kind: "direct", note_zh: "" }],
          exposure_basis: "cost",
          rationale_zh: "客製 ASIC 拉貨",
        },
      }),
    );
    expect(v.href).toBe("/item/x9");
    expect(v.affectedTickers).toEqual(["AVGO"]);
    expect(v.reason).toBe("客製 ASIC 拉貨");
    expect(v.marketFlags).toEqual([]); // live fallback carries none
    expect(v.postureLabel).toBeTruthy();
    expect(v.postureClass).toMatch(/^text-/);
  });

  it("degrades gracefully when portfolio_impact is missing", () => {
    const v = materialMoveFromItem(renderable({ id: "n1", portfolio_impact: null }));
    expect(v.affectedTickers).toEqual([]);
    expect(v.reason).toBe("");
    expect(v.href).toBe("/item/n1");
  });
});
