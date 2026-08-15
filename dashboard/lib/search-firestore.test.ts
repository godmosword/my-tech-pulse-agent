import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const loadMemoryItemsRaw = vi.fn();
const loadEarningsIndexRaw = vi.fn();
vi.mock("./json-data", () => ({
  loadMemoryItemsRaw: () => loadMemoryItemsRaw(),
  loadEarningsIndexRaw: () => loadEarningsIndexRaw(),
  itemIdOf: (row: Record<string, unknown>) => String(row.item_id || row.id || ""),
}));

const listLatestItems = vi.fn();
vi.mock("./firestore", () => ({
  listLatestItems: (...args: unknown[]) => listLatestItems(...args),
}));

const listEarningsReports = vi.fn();
vi.mock("./earnings-firestore", () => ({
  listEarningsReports: (...args: unknown[]) => listEarningsReports(...args),
}));

describe("search-firestore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadMemoryItemsRaw.mockReturnValue([]);
    loadEarningsIndexRaw.mockReturnValue([]);
    listEarningsReports.mockResolvedValue([]);
    listLatestItems.mockResolvedValue([]);
  });

  it("matches ticker on JSON items and earnings ticker lookup", async () => {
    loadMemoryItemsRaw.mockReturnValue([
      {
        item_id: "item-1",
        title: "NVDA update",
        zh_title: "NVDA 更新",
        summary: "",
        source_url: "",
        source_name: "",
        entity: "",
        category: "ai",
        kind: "instant_summary",
        score: 1,
        score_status: "ok",
        tickers: ["NVDA"],
        delivered_at: "2026-05-18T10:00:00.000Z",
      },
    ]);
    listEarningsReports.mockResolvedValueOnce([
      {
        report_id: "r1",
        ticker: "NVDA",
        company: "NVIDIA",
        quarter_label: "FY2026Q1",
        published_at_iso: "2026-05-18T10:00:00.000Z",
      },
    ]);

    const { searchPortal } = await import("./search-firestore");
    const results = await searchPortal("nvda");

    expect(listEarningsReports).toHaveBeenCalledWith({
      limit: 10,
      ticker: "NVDA",
      maxTier: 5,
    });
    expect(results.news[0]?.href).toBe("/item/item-1");
    expect(results.earnings[0]?.href).toBe("/earnings/NVDA");
  });

  it("falls back to recent in-memory scan when token queries miss", async () => {
    listLatestItems.mockResolvedValueOnce([
      {
        id: "fallback-1",
        title: "Market wrap",
        zh_title: "",
        summary: "TSMC capacity expansion drives supply chain",
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
      },
    ]);

    const { searchPortal } = await import("./search-firestore");
    const results = await searchPortal("tsmc");

    expect(listLatestItems).toHaveBeenCalledWith({ limit: 400 });
    expect(results.news).toHaveLength(1);
    expect(results.news[0]?.id).toBe("fallback-1");
    expect(results.news[0]?.href).toBe("/item/fallback-1");
  });
});
