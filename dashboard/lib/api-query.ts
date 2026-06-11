import type { NextRequest } from "next/server";

import {
  applyFilters,
  type FilterState,
  parseFilterState,
} from "./archive-filters";
import type { RenderableItem, MemoryItemKind } from "./types";

const DEFAULT_LIMIT = 40;
const MAX_LIMIT = 200;

export interface ItemListQuery {
  limit: number;
  since: Date | null;
  filters: FilterState;
  kind: MemoryItemKind | null;
  cursor: string | null;
}

export function parseItemListQuery(request: NextRequest): ItemListQuery {
  const sp = request.nextUrl.searchParams;
  const limitRaw = parseInt(sp.get("limit") ?? String(DEFAULT_LIMIT), 10);
  const limit = Number.isFinite(limitRaw)
    ? Math.min(Math.max(1, limitRaw), MAX_LIMIT)
    : DEFAULT_LIMIT;

  const sinceRaw = sp.get("since")?.trim();
  let since: Date | null = null;
  if (sinceRaw) {
    const d = new Date(sinceRaw);
    if (!Number.isNaN(d.getTime())) since = d;
  }

  const kindRaw = sp.get("kind")?.trim();
  const kind =
    kindRaw === "instant_summary" ||
    kindRaw === "deep_brief" ||
    kindRaw === "earnings"
      ? kindRaw
      : null;

  const filters = parseFilterState({
    category: sp.get("category") ?? undefined,
    month: sp.get("month") ?? undefined,
    ticker: sp.get("ticker") ?? undefined,
  });

  const cursorRaw = sp.get("cursor")?.trim();
  const cursor = cursorRaw ? cursorRaw : null;

  return { limit, since, filters, kind, cursor };
}

export function filterListedItems(
  items: RenderableItem[],
  query: ItemListQuery,
): RenderableItem[] {
  let out = applyFilters(items, query.filters);
  if (query.kind) {
    out = out.filter((i) => i.kind === query.kind);
  }
  return out.slice(0, query.limit);
}

/** Asia/Taipei midnight as UTC Date — same boundary as homepage. */
export function startOfTodayTaipeiUtc(): Date {
  const todayTpe = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Taipei",
  });
  return new Date(`${todayTpe}T00:00:00+08:00`);
}

export interface TickerRow {
  value: string;
  count: number;
}

export function aggregateTickers(
  items: RenderableItem[],
  limit = 5,
): TickerRow[] {
  const counts = new Map<string, number>();
  for (const it of items) {
    for (const t of it.tickers ?? []) {
      const key = t.trim().toUpperCase();
      if (!key) continue;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
    .slice(0, limit);
}
