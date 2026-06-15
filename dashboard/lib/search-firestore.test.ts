import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

const getMock = vi.fn();
const whereMock = vi.fn();
const orderByMock = vi.fn();
const startAtMock = vi.fn();
const endAtMock = vi.fn();
const limitMock = vi.fn();
const collectionMock = vi.fn();

function chainable() {
  const chain = {
    where: whereMock,
    orderBy: orderByMock,
    startAt: startAtMock,
    endAt: endAtMock,
    limit: limitMock,
    get: getMock,
  };
  whereMock.mockReturnValue(chain);
  orderByMock.mockReturnValue(chain);
  startAtMock.mockReturnValue(chain);
  endAtMock.mockReturnValue(chain);
  limitMock.mockReturnValue(chain);
  collectionMock.mockReturnValue(chain);
  return chain;
}

vi.mock("firebase-admin/firestore", () => ({
  getFirestore: () => ({
    collection: collectionMock,
  }),
}));

const listLatestItems = vi.fn();
vi.mock("./firestore", () => ({
  getApp: () => ({}),
  listLatestItems: (...args: unknown[]) => listLatestItems(...args),
}));

const listEarningsReports = vi.fn();
vi.mock("./earnings-firestore", () => ({
  listEarningsReports: (...args: unknown[]) => listEarningsReports(...args),
}));

describe("search-firestore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chainable();
    getMock.mockResolvedValue({ docs: [] });
    listEarningsReports.mockResolvedValue([]);
    listLatestItems.mockResolvedValue([]);
  });

  it("queries ticker array-contains and earnings ticker match", async () => {
    getMock.mockImplementation(async () => {
      const lastWhere = whereMock.mock.calls.at(-1);
      if (lastWhere?.[0] === "tickers") {
        return {
          docs: [
            {
              id: "item-1",
              data: () => ({
                id: "item-1",
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
              }),
            },
          ],
        };
      }
      return { docs: [] };
    });
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

    expect(whereMock).toHaveBeenCalledWith("tickers", "array-contains", "NVDA");
    expect(listEarningsReports).toHaveBeenCalledWith({
      limit: 10,
      ticker: "NVDA",
      maxTier: 5,
    });
    expect(results.news[0]?.href).toBe("/item/item-1");
    expect(results.earnings[0]?.href).toBe("/earnings/NVDA");
  });

  it("falls back to recent in-memory scan when Firestore queries miss", async () => {
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
