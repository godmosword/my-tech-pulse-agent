import { describe, expect, it } from "vitest";

import {
  buildDigestViewForToday,
  mergeDigestSnapshots,
  type DigestSnapshotDoc,
} from "./digest-snapshot";
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
    score: 7,
    score_status: "ok",
    hook: "",
    tickers: [],
    what_happened: "",
    why_it_matters: "",
    takeaway: null,
    published_at_iso: null,
    delivered_at_iso: "2026-05-18T10:00:00.000Z",
    themes: [],
    ...partial,
  };
}

describe("mergeDigestSnapshots", () => {
  it("unions theme items across runs without duplicating ids", () => {
    const run1: DigestSnapshotDoc = {
      digest_id: "run1",
      theme_groups: [{ theme: "AI 基礎設施", item_ids: ["a", "b"] }],
    };
    const run2: DigestSnapshotDoc = {
      digest_id: "run2",
      theme_groups: [{ theme: "AI 基礎設施", item_ids: ["b", "c"] }],
    };
    const merged = mergeDigestSnapshots([run1, run2]);
    expect(merged?.theme_groups).toEqual([
      { theme: "AI 基礎設施", item_ids: ["a", "b", "c"] },
    ]);
  });
});

describe("buildDigestViewForToday", () => {
  it("includes orphan items not listed in any snapshot", () => {
    const items = [
      item({ id: "in-snap", entity: "nvidia gpu datacenter" }),
      item({ id: "orphan", entity: "tesla ev battery", score: 6 }),
    ];
    const snapshots: DigestSnapshotDoc[] = [
      {
        digest_id: "run1",
        theme_groups: [{ theme: "AI 基礎設施", item_ids: ["in-snap"] }],
      },
    ];
    const view = buildDigestViewForToday(items, snapshots);
    const ids = view.themes.flatMap((t) => t.items.map((i) => i.id));
    expect(ids).toContain("in-snap");
    expect(ids).toContain("orphan");
    expect(view.totalShown).toBe(2);
  });

  it("includes all deep briefs from the pool", () => {
    const items = [
      item({ id: "d1", kind: "deep_brief", score: 8 }),
      item({ id: "d2", kind: "deep_brief", score: 7 }),
    ];
    const view = buildDigestViewForToday(items, []);
    expect(view.deepInsights.map((i) => i.id)).toEqual(["d1", "d2"]);
    expect(view.totalShown).toBe(2);
  });
});
