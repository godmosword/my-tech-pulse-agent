import type { MemoryItemKind, RenderableItem } from "./types";
import { priorityLevel, type PriorityLevel } from "./types";

export const HEALTH_SAMPLE_LIMIT = 120;

export const KIND_LABEL: Record<MemoryItemKind, string> = {
  instant_summary: "快訊",
  deep_brief: "深度",
  earnings: "財報",
};

export const PRIORITY_TIER_LABEL: Record<PriorityLevel, string> = {
  high: "偏高",
  med: "中等",
  low: "偏低",
};

type HealthKindCounts = Record<MemoryItemKind, number>;

type HealthPriorityCounts = Record<PriorityLevel, number>;

interface HealthSummary {
  /** Items with a non-null delivered_at, newest first. */
  delivered: RenderableItem[];
  latestDeliveredAtIso: string | null;
  countLast24h: number;
  countLast7d: number;
  kindCounts: HealthKindCounts;
  priorityCounts: HealthPriorityCounts;
  /** True when delivered sample is smaller than 5. */
  lowSample: boolean;
}

function parseDeliveredMs(iso: string | null): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

/**
 * Aggregate Firestore items for the ops health page.
 * Items without delivered_at are excluded from all "live" stats.
 */
export function summarizeHealth(
  items: RenderableItem[],
  now: Date = new Date(),
): HealthSummary {
  const nowMs = now.getTime();
  const dayMs = 24 * 60 * 60 * 1000;

  const delivered = items
    .filter((item) => parseDeliveredMs(item.delivered_at_iso) != null)
    .sort(
      (a, b) =>
        (parseDeliveredMs(b.delivered_at_iso) ?? 0) -
        (parseDeliveredMs(a.delivered_at_iso) ?? 0),
    );

  const kindCounts: HealthKindCounts = {
    instant_summary: 0,
    deep_brief: 0,
    earnings: 0,
  };
  const priorityCounts: HealthPriorityCounts = {
    high: 0,
    med: 0,
    low: 0,
  };

  let countLast24h = 0;
  let countLast7d = 0;

  // Distributions describe the same 7-day window as countLast7d, so all of the
  // summary cards read against one consistent recent period.
  for (const item of delivered) {
    const ms = parseDeliveredMs(item.delivered_at_iso)!;
    const ageMs = nowMs - ms;
    if (ageMs <= dayMs) countLast24h += 1;
    if (ageMs > 7 * dayMs) continue;
    countLast7d += 1;
    kindCounts[item.kind] += 1;
    priorityCounts[priorityLevel(item.score)] += 1;
  }

  return {
    delivered,
    latestDeliveredAtIso: delivered[0]?.delivered_at_iso ?? null,
    countLast24h,
    countLast7d,
    kindCounts,
    priorityCounts,
    lowSample: delivered.length < 5,
  };
}
