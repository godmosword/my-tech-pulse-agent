import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("server-only", () => ({}));

const listLatestItems = vi.fn();
const listLatestItemsAfter = vi.fn();
const listEarningsReports = vi.fn();
const listEarningsReportsPage = vi.fn();
const listEarningsSince = vi.fn();
const listEarningsSinceAll = vi.fn();
const getEarningsReport = vi.fn();
const buildPortfolioPayload = vi.fn();
const loadCompanyRelationships = vi.fn();
const loadClustersSnapshot = vi.fn();
const marketContextForTicker = vi.fn();
const loadTodayDigestData = vi.fn();
const latestDeliveredIso = vi.fn();
const resolveDigestView = vi.fn();

vi.mock("@/lib/firestore", () => ({
  collectionName: () => "tech_pulse_memory_items",
  listLatestItems: (...args: unknown[]) => listLatestItems(...args),
  listLatestItemsAfter: (...args: unknown[]) => listLatestItemsAfter(...args),
}));

vi.mock("@/lib/earnings-firestore", () => ({
  listEarningsReports: (...args: unknown[]) => listEarningsReports(...args),
  listEarningsReportsPage: (...args: unknown[]) => listEarningsReportsPage(...args),
  listEarningsSince: (...args: unknown[]) => listEarningsSince(...args),
  listEarningsSinceAll: (...args: unknown[]) => listEarningsSinceAll(...args),
  getEarningsReport: (...args: unknown[]) => getEarningsReport(...args),
}));

vi.mock("@/lib/portfolio-server", () => ({
  buildPortfolioPayload: (...args: unknown[]) => buildPortfolioPayload(...args),
  withPortfolioTierOnReports: <T extends { ticker: string }>(rows: T[]) => rows,
}));

vi.mock("@/lib/relationship-data", () => ({
  loadCompanyRelationships: (...args: unknown[]) => loadCompanyRelationships(...args),
  loadClustersSnapshot: (...args: unknown[]) => loadClustersSnapshot(...args),
  marketContextForTicker: (...args: unknown[]) => marketContextForTicker(...args),
}));

vi.mock("@/lib/today-digest", () => ({
  loadTodayDigestData: (...args: unknown[]) => loadTodayDigestData(...args),
  latestDeliveredIso: (...args: unknown[]) => latestDeliveredIso(...args),
}));

vi.mock("@/lib/digest-snapshot", () => ({
  resolveDigestView: (...args: unknown[]) => resolveDigestView(...args),
}));

function authedRequest(path: string): NextRequest {
  return new NextRequest(`http://localhost${path}`, {
    headers: { Authorization: "Bearer test-token" },
  });
}

describe("/api/v1 route handlers", () => {
  beforeEach(() => {
    process.env.API_READ_TOKEN = "test-token";
    delete process.env.PUBLIC_READ_MODE;
    vi.clearAllMocks();
  });

  afterEach(() => {
    delete process.env.API_READ_TOKEN;
  });

  it("GET /api/v1/health returns ok payload", async () => {
    listLatestItems.mockResolvedValue([
      { id: "x", delivered_at_iso: "2026-05-18T10:00:00.000Z" },
    ]);
    const { GET } = await import("@/app/api/v1/health/route");
    const res = await GET(authedRequest("/api/v1/health"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
    expect(body.latest_delivered_at).toBe("2026-05-18T10:00:00.000Z");
  });

  it("GET /api/v1/portfolio returns portfolio payload", async () => {
    buildPortfolioPayload.mockResolvedValue({ holdings: [], themes: [] });
    const { GET } = await import("@/app/api/v1/portfolio/route");
    const res = await GET(authedRequest("/api/v1/portfolio"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.holdings).toEqual([]);
  });

  it("GET /api/v1/earnings lists reports with count", async () => {
    listEarningsReports.mockResolvedValue([
      {
        report_id: "r1",
        ticker: "NVDA",
        quarter_label: "FY2026Q1",
        published_at_iso: "2026-05-18T10:00:00.000Z",
      },
    ]);
    const { GET } = await import("@/app/api/v1/earnings/route");
    const res = await GET(authedRequest("/api/v1/earnings?limit=5"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.count).toBe(1);
    expect(body.items[0]?.ticker).toBe("NVDA");
    expect(body.nextCursor).toBeNull();
  });

  it("GET /api/v1/earnings paginates with cursor", async () => {
    listEarningsReportsPage.mockResolvedValue({
      items: [{ report_id: "r2", ticker: "AMD", quarter_label: "FY2026Q1" }],
      hasMore: false,
      lastCursor: {
        publishedAtIso: "2026-05-17T10:00:00.000Z",
        reportId: "r2",
      },
    });
    const { encodeEarningsCursor } = await import("@/lib/pagination-cursor");
    const cursor = encodeEarningsCursor({
      publishedAtIso: "2026-05-18T10:00:00.000Z",
      reportId: "r1",
    });
    const { GET } = await import("@/app/api/v1/earnings/route");
    const res = await GET(
      authedRequest(`/api/v1/earnings?limit=5&cursor=${encodeURIComponent(cursor)}`),
    );
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.items[0]?.ticker).toBe("AMD");
    expect(body.nextCursor).toBeNull();
  });

  it("GET /api/v1/items returns nextCursor on full first page", async () => {
    listLatestItems.mockResolvedValue([
      {
        id: "item-1",
        title: "Title",
        zh_title: "",
        summary: "Summary",
        zh_summary: "摘要",
        zh_body: "",
        source_url: "https://example.com/a",
        source_name: "src",
        entity: "Co",
        category: "ai",
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
      },
      {
        id: "item-2",
        title: "Title 2",
        zh_title: "",
        summary: "Summary",
        zh_summary: "摘要",
        zh_body: "",
        source_url: "https://example.com/b",
        source_name: "src",
        entity: "Co",
        category: "ai",
        kind: "instant_summary",
        score: 7,
        score_status: "ok",
        hook: "",
        tickers: [],
        what_happened: "",
        why_it_matters: "",
        takeaway: null,
        published_at_iso: null,
        delivered_at_iso: "2026-05-17T10:00:00.000Z",
        themes: [],
      },
    ]);
    const { GET } = await import("@/app/api/v1/items/route");
    const res = await GET(authedRequest("/api/v1/items?limit=2"));
    const body = await res.json();
    expect(body.count).toBe(2);
    expect(body.nextCursor).toBeTruthy();
  });

  it("GET /api/v1/items serializes listed items", async () => {
    listLatestItems.mockResolvedValue([
      {
        id: "item-1",
        title: "Title",
        zh_title: "",
        summary: "Summary",
        zh_summary: "摘要",
        zh_body: "",
        source_url: "https://example.com/a",
        source_name: "src",
        entity: "Co",
        category: "ai",
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
      },
    ]);
    const { GET } = await import("@/app/api/v1/items/route");
    const res = await GET(authedRequest("/api/v1/items?limit=10"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.count).toBe(1);
    expect(body.items[0]?.id).toBe("item-1");
  });

  it("GET /api/v1/relationships validates ticker", async () => {
    const { GET } = await import("@/app/api/v1/relationships/route");
    const bad = await GET(authedRequest("/api/v1/relationships"));
    expect(bad.status).toBe(400);

    loadCompanyRelationships.mockReturnValue({
      ticker: "NVDA",
      edges: [],
      source_form: "10-K",
    });
    loadClustersSnapshot.mockReturnValue({ clusters: [] });
    marketContextForTicker.mockReturnValue({ correlated: [] });

    const ok = await GET(authedRequest("/api/v1/relationships?ticker=NVDA"));
    expect(ok.status).toBe(200);
    const body = await ok.json();
    expect(body.business.ticker).toBe("NVDA");
  });

  it("GET /api/v1/earnings/report/[reportId] returns 404 when missing", async () => {
    getEarningsReport.mockResolvedValue(null);
    const { GET } = await import("@/app/api/v1/earnings/report/[reportId]/route");
    const res = await GET(
      authedRequest("/api/v1/earnings/report/missing-id"),
      { params: Promise.resolve({ reportId: "missing-id" }) },
    );
    expect(res.status).toBe(404);
  });

  it("withApiAuth returns 503 when API_READ_TOKEN unset", async () => {
    delete process.env.API_READ_TOKEN;
    process.env.PUBLIC_READ_MODE = "0";
    const { GET } = await import("@/app/api/v1/health/route");
    const res = await GET(new NextRequest("http://localhost/api/v1/health"));
    expect(res.status).toBe(503);
  });

  it("withApiAuth returns 401 when token configured but missing bearer", async () => {
    process.env.API_READ_TOKEN = "test-token";
    process.env.PUBLIC_READ_MODE = "0";
    const { GET } = await import("@/app/api/v1/health/route");
    const res = await GET(new NextRequest("http://localhost/api/v1/health"));
    expect(res.status).toBe(401);
  });

  it("GET /api/v1/tickers aggregates symbols", async () => {
    listLatestItems.mockResolvedValue([
      { tickers: ["NVDA", "AMD"], delivered_at_iso: "2026-05-18T10:00:00.000Z" },
      { tickers: ["NVDA"], delivered_at_iso: "2026-05-18T11:00:00.000Z" },
    ]);
    const { GET } = await import("@/app/api/v1/tickers/route");
    const res = await GET(authedRequest("/api/v1/tickers?limit=3"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.tickers[0]?.value).toBe("NVDA");
    expect(body.tickers[0]?.count).toBe(2);
  });

  it("GET /api/v1/digest/today returns digest payload", async () => {
    loadTodayDigestData.mockResolvedValue({
      items: [{ id: "a", delivered_at_iso: "2026-05-18T10:00:00.000Z" }],
      snapshots: [],
      usingStaleFallback: false,
    });
    latestDeliveredIso.mockReturnValue("2026-05-18T10:00:00.000Z");
    resolveDigestView.mockReturnValue({
      deepInsights: [],
      themes: [{ theme: "AI", items: [] }],
      totalShown: 0,
      averageScore: 0,
    });

    const { GET } = await import("@/app/api/v1/digest/today/route");
    const res = await GET(authedRequest("/api/v1/digest/today"));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.timezone).toBe("Asia/Taipei");
    expect(body.digest.themes[0]?.theme).toBe("AI");
  });
});
