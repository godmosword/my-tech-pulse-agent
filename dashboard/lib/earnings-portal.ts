import "server-only";

import watchlistData from "./earnings-watchlist-data.json";
import {
  listEarningsReports,
  type EarningsReportRow,
} from "./earnings-firestore";
import {
  pillarFor,
  watchlistTickerSet,
  type WatchlistEntryRow,
} from "./pillar-map";

export type { WatchlistEntryRow };

const WATCHLIST: WatchlistEntryRow[] = (
  watchlistData as { entries: WatchlistEntryRow[] }
).entries.map((e) => ({
  ticker: e.ticker.toUpperCase(),
  tier: e.tier ?? null,
  tags: e.tags ?? [],
}));

const WATCHLIST_SET = watchlistTickerSet();

export function watchlistEntries(): WatchlistEntryRow[] {
  return WATCHLIST;
}

function anchorDateUtc(): Date {
  return new Date();
}

function formatYmd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

type CalendarCache = {
  key: string;
  expires: number;
  rows: FinnhubCalendarRow[];
};

let calendarCache: CalendarCache | null = null;
const CALENDAR_TTL_MS = 3600_000;

interface FinnhubCalendarRow {
  symbol?: string;
  date?: string;
  epsEstimate?: number;
  quarter?: number;
  year?: number;
}

async function fetchFinnhubCalendar(
  from: string,
  to: string,
): Promise<FinnhubCalendarRow[]> {
  const key = process.env.FINNHUB_API_KEY?.trim();
  if (!key) return [];

  const cacheKey = `${from}:${to}`;
  if (calendarCache && calendarCache.key === cacheKey && calendarCache.expires > Date.now()) {
    return calendarCache.rows;
  }

  const url = new URL("https://finnhub.io/api/v1/calendar/earnings");
  url.searchParams.set("from", from);
  url.searchParams.set("to", to);
  url.searchParams.set("token", key);

  const timeoutMs = Number(process.env.FINNHUB_HTTP_TIMEOUT_SEC || 10) * 1000;
  try {
    const resp = await fetch(url.toString(), {
      signal: AbortSignal.timeout(timeoutMs),
      headers: { Accept: "application/json" },
      next: { revalidate: 0 },
    });
    if (!resp.ok) return [];
    const data = (await resp.json()) as {
      earningsCalendar?: FinnhubCalendarRow[];
    };
    const rows = data.earningsCalendar ?? [];
    calendarCache = {
      key: cacheKey,
      expires: Date.now() + CALENDAR_TTL_MS,
      rows,
    };
    return rows;
  } catch (err) {
    console.warn("[earnings-portal] Finnhub calendar failed", err);
    return [];
  }
}

export interface UpcomingEarningsItem {
  symbol: string;
  pillar: string;
  next_earnings_date: string;
  days_until: number;
  status: string;
  tier: number | null;
  source: "finnhub" | "recent_filing";
}

export async function loadUpcomingEarnings(days: number): Promise<{
  as_of: string;
  days: number;
  watchlist_size: number;
  items: UpcomingEarningsItem[];
  calendar_source: string;
}> {
  const anchor = anchorDateUtc();
  const asOf = formatYmd(anchor);
  const end = new Date(anchor);
  end.setUTCDate(end.getUTCDate() + days);
  const endStr = formatYmd(end);

  const items: UpcomingEarningsItem[] = [];
  const seen = new Set<string>();

  const finnhubRows = await fetchFinnhubCalendar(asOf, endStr);
  for (const row of finnhubRows) {
    const sym = String(row.symbol || "").toUpperCase();
    const ed = String(row.date || "").slice(0, 10);
    if (!sym || !ed || !WATCHLIST_SET.has(sym) || seen.has(sym)) continue;
    const eventDate = new Date(`${ed}T12:00:00Z`);
    const daysUntil = Math.round(
      (eventDate.getTime() - anchor.getTime()) / 86_400_000,
    );
    if (daysUntil < 0 || daysUntil > days) continue;
    seen.add(sym);
    const tier = WATCHLIST.find((e) => e.ticker === sym)?.tier ?? null;
    items.push({
      symbol: sym,
      pillar: pillarFor(sym),
      next_earnings_date: ed,
      days_until: daysUntil,
      status: "unknown",
      tier,
      source: "finnhub",
    });
  }

  // No fallback to recently *published* reports: those are past filings, and
  // surfacing them under a "next N days" header (with a bogus days_until: 0)
  // is misleading. Recent filings already have their own "剛公布" surfaces.
  const calendarSource = finnhubRows.length ? "finnhub" : "none";

  items.sort((a, b) => a.days_until - b.days_until || a.symbol.localeCompare(b.symbol));

  return {
    as_of: asOf,
    days,
    watchlist_size: WATCHLIST.length,
    items,
    calendar_source: calendarSource,
  };
}

export interface EarningsInsightResponse {
  enabled: boolean;
  symbol: string;
  reason?: string;
  hint?: string;
  report?: EarningsReportRow;
  report_url_path?: string;
}

export async function loadEarningsInsight(symbol: string): Promise<EarningsInsightResponse> {
  const sym = symbol.trim().toUpperCase();
  if (!sym || !/^[A-Z0-9.-]{1,12}$/.test(sym)) {
    return {
      enabled: false,
      symbol: sym || symbol,
      reason: "invalid_symbol",
    };
  }

  const reports = await listEarningsReports({ ticker: sym, limit: 5, maxTier: 5 });
  const best =
    reports.find((r) => r.schema_version === "earnings_v3" && r.rendered_markdown_zh) ||
    reports[0];

  if (!best) {
    return {
      enabled: false,
      symbol: sym,
      reason: "no_earnings_report",
      hint: "Run tech-pulse earnings pipeline or backfill for this ticker.",
    };
  }

  return {
    enabled: true,
    symbol: sym,
    report: best,
    report_url_path: `/earnings/report/${encodeURIComponent(best.report_id)}`,
  };
}
