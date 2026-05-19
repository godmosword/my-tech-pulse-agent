import type { PriorityLevel, RenderableItem } from "./types";
import { priorityLevel } from "./types";
import { categoryLabel } from "./digest";

export interface FilterState {
  category: string | null;
  month: string | null;
  priority: PriorityLevel | null;
}

export interface Facet {
  value: string;
  label: string;
  count: number;
}

export interface ArchiveFacets {
  categories: Facet[];
  months: Facet[];
}

const VALID_PRIORITIES = new Set<string>(["high", "med", "low"]);

export function parseFilterState(
  searchParams: Record<string, string | string[] | undefined> | undefined,
): FilterState {
  const pick = (key: string): string | null => {
    const v = searchParams?.[key];
    const s = Array.isArray(v) ? v[0] : v;
    const t = (s ?? "").trim();
    return t ? t : null;
  };
  const rawPriority = pick("priority");
  return {
    category: pick("category"),
    month: pick("month"),
    priority: rawPriority && VALID_PRIORITIES.has(rawPriority)
      ? (rawPriority as PriorityLevel)
      : null,
  };
}

/** "2026-05-18T..." → "2026-05"; empty/invalid → "". */
export function monthKey(iso: string | null | undefined): string {
  if (!iso || iso.length < 7) return "";
  return iso.slice(0, 7);
}

export function monthLabel(key: string): string {
  if (!key || key.length !== 7) return key || "";
  const [y, m] = key.split("-");
  const n = parseInt(m ?? "", 10);
  if (!y || !Number.isFinite(n)) return key;
  return `${y} 年 ${n} 月`;
}

export function buildFacets(items: RenderableItem[]): ArchiveFacets {
  const catCounts = new Map<string, number>();
  const monthCounts = new Map<string, number>();
  for (const item of items) {
    const c = (item.category || "").toLowerCase();
    if (c) catCounts.set(c, (catCounts.get(c) ?? 0) + 1);
    const mk = monthKey(item.delivered_at_iso);
    if (mk) monthCounts.set(mk, (monthCounts.get(mk) ?? 0) + 1);
  }
  const categories: Facet[] = [...catCounts.entries()]
    .map(([value, count]) => ({ value, label: categoryLabel(value), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  const months: Facet[] = [...monthCounts.entries()]
    .map(([value, count]) => ({ value, label: monthLabel(value), count }))
    // newest month first
    .sort((a, b) => b.value.localeCompare(a.value));
  return { categories, months };
}

export function applyFilters(
  items: RenderableItem[],
  state: FilterState,
): RenderableItem[] {
  const cat = state.category?.toLowerCase() ?? null;
  const mo = state.month ?? null;
  const pri = state.priority ?? null;
  return items.filter((item) => {
    if (cat && (item.category || "").toLowerCase() !== cat) return false;
    if (mo && monthKey(item.delivered_at_iso) !== mo) return false;
    if (pri) {
      const level = priorityLevel(item.score);
      if (level !== pri) return false;
    }
    return true;
  });
}

/** Build /archive?... preserving other params but replacing one key.
 *  Pass `null` to clear that key. */
export function buildArchiveHref(
  current: FilterState,
  patch: Partial<FilterState>,
): string {
  const next: FilterState = { ...current, ...patch };
  const params = new URLSearchParams();
  if (next.category) params.set("category", next.category);
  if (next.month) params.set("month", next.month);
  if (next.priority) params.set("priority", next.priority);
  const qs = params.toString();
  return qs ? `/archive?${qs}` : "/archive";
}
