import type { ItemListQuery } from "./api-query";
import { filterListedItems } from "./api-query";
import { listLatestItemsAfter } from "./firestore";
import {
  decodeItemCursor,
  encodeItemCursor,
  type ItemCursor,
} from "./pagination-cursor";
import type { RenderableItem } from "./types";

const FIRESTORE_BATCH = 80;
const MAX_FIRESTORE_SCAN = 400;

export interface ItemsPageResult {
  items: RenderableItem[];
  nextCursor: string | null;
}

function itemCursorFrom(item: RenderableItem): ItemCursor | null {
  if (!item.delivered_at_iso) return null;
  return {
    deliveredAtIso: item.delivered_at_iso,
    id: item.id,
  };
}

function matchesQuery(item: RenderableItem, query: ItemListQuery): boolean {
  return filterListedItems([item], { ...query, limit: Number.MAX_SAFE_INTEGER })
    .length > 0;
}

export async function listFilteredItemsPage(
  query: ItemListQuery,
  cursorRaw?: string | null,
): Promise<ItemsPageResult> {
  const cursor = decodeItemCursor(cursorRaw);
  if (cursorRaw && !cursor) {
    return { items: [], nextCursor: null };
  }

  const collected: RenderableItem[] = [];
  let scanCursor: ItemCursor | null | undefined = cursor;
  let scanned = 0;
  let hasMoreInFirestore = true;

  while (collected.length < query.limit && hasMoreInFirestore && scanned < MAX_FIRESTORE_SCAN) {
    const batchLimit = Math.min(FIRESTORE_BATCH, MAX_FIRESTORE_SCAN - scanned);
    const batch = await listLatestItemsAfter({
      limit: batchLimit,
      since: query.since ?? undefined,
      cursor: scanCursor
        ? { deliveredAtIso: scanCursor.deliveredAtIso, id: scanCursor.id }
        : undefined,
    });
    scanned += batch.items.length;
    hasMoreInFirestore = batch.hasMore;
    scanCursor = batch.lastCursor
      ? { deliveredAtIso: batch.lastCursor.deliveredAtIso, id: batch.lastCursor.id }
      : null;

    for (const item of batch.items) {
      if (!matchesQuery(item, query)) continue;
      collected.push(item);
      if (collected.length >= query.limit) break;
    }

    if (!batch.hasMore) break;
  }

  const items = collected.slice(0, query.limit);
  const lastItem = items.at(-1);
  const lastCursor = lastItem ? itemCursorFrom(lastItem) : null;
  const hasAnotherPage =
    collected.length > query.limit ||
    (collected.length === query.limit && hasMoreInFirestore);

  return {
    items,
    nextCursor:
      lastCursor && hasAnotherPage ? encodeItemCursor(lastCursor) : null,
  };
}

/** First-page fetch matching legacy GET /api/v1/items (no cursor param). */
export async function listFilteredItemsLegacy(
  query: ItemListQuery,
  fetchFromFirestore: (opts: { limit: number; since?: Date }) => Promise<RenderableItem[]>,
): Promise<ItemsPageResult> {
  const fetchLimit = Math.min(query.limit * 4, 400);
  const items = await fetchFromFirestore({
    limit: fetchLimit,
    since: query.since ?? undefined,
  });
  const filtered = filterListedItems(items, query);
  const lastItem = filtered.at(-1);
  const lastCursor = lastItem ? itemCursorFrom(lastItem) : null;
  const nextCursor =
    lastCursor && filtered.length === query.limit
      ? encodeItemCursor(lastCursor)
      : null;
  return { items: filtered, nextCursor };
}
