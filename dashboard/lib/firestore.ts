import "server-only";

import {
  deliveredMs,
  itemIdOf,
  loadDigestSnapshotsRaw,
  loadMemoryItemsRaw,
  publishedMs,
} from "./json-data";
import {
  MemoryItemSchema,
  toIsoString,
  type RenderableItem,
} from "./types";

const COLLECTION = "tech_pulse_memory_items";

function toRenderable(id: string, raw: unknown): RenderableItem | null {
  const parsed = MemoryItemSchema.safeParse({ ...(raw as object), id });
  if (!parsed.success) return null;
  const item = parsed.data;
  const themes = item.category ? [item.category] : [];
  return {
    id: item.id,
    title: item.title,
    zh_title: item.zh_title ?? "",
    summary: item.summary,
    zh_summary: item.zh_summary ?? "",
    zh_body: item.zh_body ?? "",
    source_url: item.source_url,
    source_name: item.source_name,
    entity: item.entity,
    category: item.category,
    kind: item.kind,
    score: item.score,
    score_status: item.score_status,
    hook: item.hook ?? "",
    tickers: item.tickers ?? [],
    what_happened: item.what_happened ?? "",
    why_it_matters: item.why_it_matters ?? "",
    takeaway: item.takeaway?.takeaway_zh
      ? {
          item_id: item.takeaway.item_id ?? item.id,
          takeaway_zh: item.takeaway.takeaway_zh ?? "",
          angle: item.takeaway.angle ?? "其他",
          tickers: item.takeaway.tickers ?? [],
          confidence: item.takeaway.confidence ?? "medium",
        }
      : null,
    portfolio_impact: item.portfolio_impact ?? null,
    published_at_iso: toIsoString(item.published_at),
    delivered_at_iso: toIsoString(item.delivered_at),
    themes,
  };
}

function allRenderable(): RenderableItem[] {
  const rows = loadMemoryItemsRaw();
  const items: RenderableItem[] = [];
  for (const row of rows) {
    const id = itemIdOf(row);
    if (!id) continue;
    const rendered = toRenderable(id, row);
    if (rendered) items.push(rendered);
  }
  items.sort((a, b) => {
    const aMs = a.delivered_at_iso ? Date.parse(a.delivered_at_iso) : 0;
    const bMs = b.delivered_at_iso ? Date.parse(b.delivered_at_iso) : 0;
    if (bMs !== aMs) return bMs - aMs;
    return b.id.localeCompare(a.id);
  });
  return items;
}

export interface ListOptions {
  limit?: number;
  since?: Date;
}

export interface ItemFirestoreCursor {
  deliveredAtIso: string;
  id: string;
}

function applySince(items: RenderableItem[], since?: Date): RenderableItem[] {
  if (!since) return items;
  const sinceMs = since.getTime();
  return items.filter((item) => {
    if (!item.delivered_at_iso) return false;
    return Date.parse(item.delivered_at_iso) >= sinceMs;
  });
}

export async function listLatestItems({
  limit = 60,
  since,
}: ListOptions = {}): Promise<RenderableItem[]> {
  return applySince(allRenderable(), since).slice(0, limit);
}

export async function listLatestItemsAfter({
  limit,
  since,
  cursor,
}: {
  limit: number;
  since?: Date;
  cursor?: ItemFirestoreCursor;
}): Promise<{
  items: RenderableItem[];
  hasMore: boolean;
  lastCursor: ItemFirestoreCursor | null;
}> {
  let items = applySince(allRenderable(), since);
  if (cursor) {
    const cursorMs = Date.parse(cursor.deliveredAtIso);
    items = items.filter((item) => {
      const ms = item.delivered_at_iso ? Date.parse(item.delivered_at_iso) : 0;
      if (ms < cursorMs) return true;
      if (ms > cursorMs) return false;
      return item.id < cursor.id;
    });
  }
  const page = items.slice(0, limit);
  const last = page.at(-1);
  return {
    items: page,
    hasMore: items.length > limit,
    lastCursor:
      last && last.delivered_at_iso
        ? { deliveredAtIso: last.delivered_at_iso, id: last.id }
        : null,
  };
}

export async function getItemById(id: string): Promise<RenderableItem | null> {
  const row = loadMemoryItemsRaw().find((item) => itemIdOf(item) === id);
  if (!row) return null;
  return toRenderable(id, row);
}

export function collectionName(): string {
  return COLLECTION;
}

/** All digest snapshots since a boundary (ascending — oldest run first). */
export async function listDigestSnapshotsSince(
  since: Date,
  { limit = 24 }: { limit?: number } = {},
): Promise<Record<string, unknown>[]> {
  const sinceMs = since.getTime();
  const rows = loadDigestSnapshotsRaw()
    .filter((row) => deliveredMs(row) >= sinceMs || publishedMs(row) >= sinceMs)
    .sort((a, b) => deliveredMs(a) - deliveredMs(b));
  return rows.slice(0, limit).map((row) => ({
    ...row,
    digest_id: String(row.digest_id || ""),
  }));
}
