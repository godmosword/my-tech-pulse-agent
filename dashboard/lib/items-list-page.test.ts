import { describe, expect, it, vi } from "vitest";

import type { ItemListQuery } from "./api-query";
import {
  listFilteredItemsLegacy,
  listFilteredItemsPage,
} from "./items-list-page";
import { encodeItemCursor } from "./pagination-cursor";
import type { RenderableItem } from "./types";

function sampleItem(id: string, deliveredAt: string, category = "ai"): RenderableItem {
  return {
    id,
    title: id,
    zh_title: "",
    summary: "",
    zh_summary: "",
    zh_body: "",
    source_url: "https://example.com",
    source_name: "src",
    entity: "Co",
    category,
    kind: "instant_summary",
    score: 7,
    score_status: "ok",
    hook: "",
    tickers: ["NVDA"],
    what_happened: "",
    why_it_matters: "",
    takeaway: null,
    published_at_iso: null,
    delivered_at_iso: deliveredAt,
    themes: [],
  };
}

const baseQuery: ItemListQuery = {
  limit: 2,
  since: null,
  filters: { category: null, month: null, ticker: null },
  kind: null,
  cursor: null,
};

vi.mock("./firestore", () => ({
  listLatestItemsAfter: vi.fn(),
}));

import { listLatestItemsAfter } from "./firestore";

describe("items-list-page", () => {
  it("legacy path slices filtered items and sets nextCursor when full page", async () => {
    const fetch = vi.fn().mockResolvedValue([
      sampleItem("a", "2026-05-18T10:00:00.000Z"),
      sampleItem("b", "2026-05-17T10:00:00.000Z"),
      sampleItem("c", "2026-05-16T10:00:00.000Z"),
    ]);
    const page = await listFilteredItemsLegacy(baseQuery, fetch);
    expect(page.items.map((i) => i.id)).toEqual(["a", "b"]);
    expect(page.nextCursor).toBe(
      encodeItemCursor({
        deliveredAtIso: "2026-05-17T10:00:00.000Z",
        id: "b",
      }),
    );
  });

  it("cursor path scans firestore batches until page filled", async () => {
    const mocked = vi.mocked(listLatestItemsAfter);
    mocked
      .mockResolvedValueOnce({
        items: [sampleItem("a", "2026-05-18T10:00:00.000Z", "macro")],
        hasMore: true,
        lastCursor: {
          deliveredAtIso: "2026-05-18T10:00:00.000Z",
          id: "a",
        },
      })
      .mockResolvedValueOnce({
        items: [
          sampleItem("b", "2026-05-17T10:00:00.000Z"),
          sampleItem("c", "2026-05-16T10:00:00.000Z"),
        ],
        hasMore: false,
        lastCursor: {
          deliveredAtIso: "2026-05-16T10:00:00.000Z",
          id: "c",
        },
      });

    const cursor = encodeItemCursor({
      deliveredAtIso: "2026-05-19T10:00:00.000Z",
      id: "z",
    });
    const page = await listFilteredItemsPage(
      {
        ...baseQuery,
        filters: { category: "ai", month: null, ticker: null },
      },
      cursor,
    );
    expect(page.items.map((i) => i.id)).toEqual(["b", "c"]);
    expect(mocked).toHaveBeenCalledTimes(2);
  });
});
