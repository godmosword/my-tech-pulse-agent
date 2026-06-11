import { listEarningsSince, listEarningsSinceAll } from "./earnings-firestore";
import {
  decodeSignalCursor,
  encodeSignalCursor,
} from "./pagination-cursor";
import type { PortfolioTier } from "./portfolio-metrics";
import { classifyTier } from "./portfolio-metrics";

const CONVICTION_RANK: Record<string, number> = {
  low: 0,
  medium: 1,
  high: 2,
};

export interface SignalListItem {
  ticker: string;
  quarter_label: string;
  score: number;
  rating: string;
  conviction: string;
  top_factor: string | null;
  report_id: string;
  portfolio_tier: PortfolioTier;
  factors: Array<{ name: string; score: number | null; available: boolean }>;
}

export interface SignalsQuery {
  days: number;
  minConviction?: string;
  tierFilter?: string;
  limit?: number;
  cursor?: string | null;
}

export interface SignalsPageResult {
  items: SignalListItem[];
  nextCursor: string | null;
}

function mapSignalRows(
  rows: Awaited<ReturnType<typeof listEarningsSinceAll>>,
  holdingsSet: Set<string>,
  watchlistSet: Set<string>,
): SignalListItem[] {
  return rows
    .filter((r) => r.investment_signal?.score != null)
    .map((r) => {
      const sig = r.investment_signal!;
      const top = [...(sig.factors || [])]
        .filter((f) => f.available && f.score != null)
        .sort((a, b) => (b.weight || 0) - (a.weight || 0))[0];
      return {
        ticker: r.ticker,
        quarter_label: r.quarter_label,
        score: sig.score as number,
        rating: sig.rating,
        conviction: sig.conviction,
        top_factor: top?.name ?? null,
        report_id: r.report_id,
        portfolio_tier: classifyTier(r.ticker, holdingsSet, watchlistSet),
        factors: (sig.factors ?? []).map((f) => ({
          name: f.name,
          score: f.score ?? null,
          available: f.available,
        })),
      };
    });
}

function applySignalFilters(
  items: SignalListItem[],
  query: SignalsQuery,
): SignalListItem[] {
  let out = items;
  if (query.minConviction === "medium") {
    out = out.filter((i) => (CONVICTION_RANK[i.conviction] ?? 0) >= 1);
  } else if (query.minConviction === "high") {
    out = out.filter((i) => i.conviction === "high");
  }

  if (query.tierFilter === "holding") {
    out = out.filter((i) => i.portfolio_tier === "holding");
  } else if (query.tierFilter === "watchlist") {
    out = out.filter((i) => i.portfolio_tier === "watchlist");
  }

  out.sort((a, b) => b.score - a.score);
  return out;
}

function sliceAfterCursor(
  items: SignalListItem[],
  cursorRaw?: string | null,
): SignalListItem[] {
  const cursor = decodeSignalCursor(cursorRaw);
  if (!cursorRaw) return items;
  if (!cursor) return [];

  const start = items.findIndex(
    (item) => item.report_id === cursor.reportId && item.score === cursor.score,
  );
  if (start < 0) return [];
  return items.slice(start + 1);
}

export async function listSignalsPage(
  query: SignalsQuery,
  holdingsSet: Set<string>,
  watchlistSet: Set<string>,
): Promise<SignalsPageResult> {
  const since = new Date();
  since.setUTCDate(since.getUTCDate() - query.days);

  const rows = await listEarningsSinceAll(since, { maxTier: 5 });
  const filtered = applySignalFilters(
    mapSignalRows(rows, holdingsSet, watchlistSet),
    query,
  );

  const afterCursor = sliceAfterCursor(filtered, query.cursor);
  if (query.cursor && afterCursor.length === 0 && filtered.length > 0) {
    return { items: [], nextCursor: null };
  }

  if (!query.limit) {
    return { items: afterCursor, nextCursor: null };
  }

  const page = afterCursor.slice(0, query.limit);
  const last = page.at(-1);
  const hasMore = afterCursor.length > query.limit;

  return {
    items: page,
    nextCursor:
      last && hasMore
        ? encodeSignalCursor({ score: last.score, reportId: last.report_id })
        : null,
  };
}

/** Legacy signals list (no limit / cursor params) — same item set as before pagination. */
export async function listSignalsLegacy(
  query: Omit<SignalsQuery, "limit" | "cursor">,
  holdingsSet: Set<string>,
  watchlistSet: Set<string>,
): Promise<SignalsPageResult> {
  const since = new Date();
  since.setUTCDate(since.getUTCDate() - query.days);

  const rows = await listEarningsSince(since, { limit: 120, maxTier: 5 });
  const items = applySignalFilters(
    mapSignalRows(rows, holdingsSet, watchlistSet),
    query,
  );
  return { items, nextCursor: null };
}
