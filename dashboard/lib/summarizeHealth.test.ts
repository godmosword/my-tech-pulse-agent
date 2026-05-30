import { describe, expect, it } from "vitest";

import { summarizeHealth } from "./summarizeHealth";
import type { RenderableItem } from "./types";

function item(
  partial: Partial<RenderableItem> & Pick<RenderableItem, "id">,
): RenderableItem {
  return {
    title: "Title",
    zh_title: "",
    summary: "",
    zh_summary: "",
    zh_body: "",
    source_url: "",
    source_name: "Source",
    entity: "",
    category: "",
    kind: "instant_summary",
    score: 6,
    score_status: "ok",
    hook: "",
    tickers: [],
    what_happened: "",
    why_it_matters: "",
    takeaway: null,
    published_at_iso: null,
    delivered_at_iso: null,
    themes: [],
    ...partial,
  };
}

describe("summarizeHealth", () => {
  const now = new Date("2026-05-18T12:00:00.000Z");

  it("excludes items without delivered_at from stats", () => {
    const summary = summarizeHealth(
      [
        item({ id: "a", delivered_at_iso: "2026-05-18T10:00:00.000Z" }),
        item({ id: "b", delivered_at_iso: null }),
      ],
      now,
    );
    expect(summary.delivered).toHaveLength(1);
    expect(summary.delivered[0]?.id).toBe("a");
  });

  it("counts 24h / 7d windows and scopes distributions to the 7d window", () => {
    const summary = summarizeHealth(
      [
        item({
          id: "recent",
          kind: "deep_brief",
          delivered_at_iso: "2026-05-18T08:00:00.000Z",
          score: 8.5,
        }),
        item({
          id: "week",
          kind: "instant_summary",
          delivered_at_iso: "2026-05-12T08:00:00.000Z",
          score: 4,
        }),
        item({
          id: "week-earnings",
          kind: "earnings",
          delivered_at_iso: "2026-05-13T08:00:00.000Z",
          score: 6,
        }),
        // Older than 7d: excluded from countLast7d and from both distributions.
        item({
          id: "old",
          kind: "earnings",
          delivered_at_iso: "2026-05-01T08:00:00.000Z",
          score: 6,
        }),
      ],
      now,
    );

    expect(summary.countLast24h).toBe(1);
    expect(summary.countLast7d).toBe(3);
    expect(summary.kindCounts.deep_brief).toBe(1);
    expect(summary.kindCounts.instant_summary).toBe(1);
    expect(summary.kindCounts.earnings).toBe(1);
    expect(summary.priorityCounts.high).toBe(1);
    expect(summary.priorityCounts.med).toBe(1);
    expect(summary.priorityCounts.low).toBe(1);
    // Distribution totals reconcile with the 7d window.
    const kindTotal =
      summary.kindCounts.deep_brief +
      summary.kindCounts.instant_summary +
      summary.kindCounts.earnings;
    expect(kindTotal).toBe(summary.countLast7d);
    expect(summary.latestDeliveredAtIso).toBe("2026-05-18T08:00:00.000Z");
  });

  it("flags low sample when fewer than five delivered items", () => {
    const summary = summarizeHealth(
      [item({ id: "only", delivered_at_iso: "2026-05-18T08:00:00.000Z" })],
      now,
    );
    expect(summary.lowSample).toBe(true);
  });
});
