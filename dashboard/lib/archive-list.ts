import { categoryLabel } from "./digest";
import type { ApiItem } from "./api-serialize";
import type { RenderableItem } from "./types";
import { displayTitle, listingZhSubline } from "./types";

export interface ArchiveListItem {
  id: string;
  title: string;
  subline: string | null;
  kind: string;
  category: string;
  sourceName: string;
  deliveredAtIso: string;
  publishedAtIso: string | null;
}

export function archiveItemFromRenderable(item: RenderableItem): ArchiveListItem {
  return {
    id: item.id,
    title: displayTitle(item),
    subline: listingZhSubline(item),
    kind: item.kind,
    category: item.category,
    sourceName: item.source_name,
    deliveredAtIso: item.delivered_at_iso ?? "",
    publishedAtIso: item.published_at_iso,
  };
}

export function archiveItemFromApi(item: ApiItem): ArchiveListItem {
  return {
    id: item.id,
    title: item.title_zh || item.title_en,
    subline: item.summary_zh,
    kind: item.kind,
    category: item.category,
    sourceName: item.source_name,
    deliveredAtIso: item.delivered_at ?? "",
    publishedAtIso: item.published_at,
  };
}

export function archiveKickerSegments(item: ArchiveListItem): string[] {
  const parts: string[] = [];
  if (item.kind === "deep_brief") parts.push("Deep Insight");
  else if (item.kind === "earnings") parts.push("Earnings");

  if (item.category?.trim()) {
    parts.push(categoryLabel(item.category));
  }

  const source = item.sourceName?.trim();
  if (source) parts.push(source);

  return parts;
}

function itemBestTimestamp(item: ArchiveListItem): string {
  return item.publishedAtIso || item.deliveredAtIso || "";
}

export interface ArchiveDayBucket {
  dayIso: string;
  items: ArchiveListItem[];
}

export function bucketArchiveByDay(items: ArchiveListItem[]): ArchiveDayBucket[] {
  const groups = new Map<string, ArchiveListItem[]>();
  for (const item of items) {
    const key = itemBestTimestamp(item).slice(0, 10) || "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => itemBestTimestamp(b).localeCompare(itemBestTimestamp(a)));
  }
  return [...groups.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([dayIso, dayItems]) => ({ dayIso, items: dayItems }));
}

/**
 * Server-safe seed for the archive list's first render. Lives here (not in the
 * `"use client"` ArchiveList) so the server page can call it without tripping
 * Next's "can't call a client function from the server" boundary error.
 */
export function toInitialArchiveBuckets(
  items: ArchiveListItem[],
): ArchiveDayBucket[] {
  return bucketArchiveByDay(items);
}

export function mergeArchiveBuckets(
  existing: ArchiveDayBucket[],
  moreItems: ArchiveListItem[],
): ArchiveDayBucket[] {
  const flat = [
    ...existing.flatMap((bucket) => bucket.items),
    ...moreItems,
  ];
  return bucketArchiveByDay(flat);
}
