import "server-only";

import { cache } from "react";

import { startOfTodayTaipeiUtc } from "./api-query";
import { parseDigestSnapshot } from "./digest-snapshot";
import type { DigestSnapshotDoc } from "./digest-snapshot";
import { listDigestSnapshotsSince, listLatestItems } from "./firestore";
import type { RenderableItem } from "./types";

/** Max memory items loaded for the homepage / digest API (single Taipei day). */
const TODAY_ITEMS_LIMIT = 100;

/** Max pipeline digest snapshots merged per day. */
const TODAY_SNAPSHOT_LIMIT = 48;

export interface TodayDigestLoadResult {
  items: RenderableItem[];
  snapshots: DigestSnapshotDoc[];
  /** True when today's pool is empty and we show the latest delivery batch instead. */
  usingStaleFallback: boolean;
  todayStart: Date;
}

/**
 * Loads items + snapshots for the Today view.
 * Degrades to empty arrays on Firestore failure (matches AttentionTriage).
 * When falling back to stale items, skips today's snapshots so theme hints
 * stay consistent with the displayed pool.
 *
 * Exported uncached for unit tests; the request-scoped `loadTodayDigestData`
 * below memoizes it so the home page and its `@rail` parallel route share a
 * single Firestore read per request instead of fetching twice.
 */
export async function loadTodayDigestDataUncached(): Promise<TodayDigestLoadResult> {
  const todayStart = startOfTodayTaipeiUtc();
  try {
    let items = await listLatestItems({
      limit: TODAY_ITEMS_LIMIT,
      since: todayStart,
    });
    let usingStaleFallback = false;
    if (items.length === 0) {
      items = await listLatestItems({ limit: TODAY_ITEMS_LIMIT });
      usingStaleFallback = items.length > 0;
    }

    const snapshotRows = usingStaleFallback
      ? []
      : await listDigestSnapshotsSince(todayStart, {
          limit: TODAY_SNAPSHOT_LIMIT,
        });
    const snapshots = snapshotRows.map(parseDigestSnapshot);

    return { items, snapshots, usingStaleFallback, todayStart };
  } catch {
    return {
      items: [],
      snapshots: [],
      usingStaleFallback: false,
      todayStart,
    };
  }
}

/**
 * Request-scoped memoized loader. React `cache()` dedupes calls within a single
 * server request, so `app/(app)/page.tsx` and `app/(app)/@rail/page.tsx` (which
 * both need today's items) hit Firestore once instead of twice.
 */
export const loadTodayDigestData = cache(loadTodayDigestDataUncached);

export function latestDeliveredIso(items: RenderableItem[]): string | null {
  return (
    items
      .map((i) => i.delivered_at_iso)
      .filter((iso): iso is string => Boolean(iso))
      .sort()
      .reverse()[0] ?? null
  );
}
