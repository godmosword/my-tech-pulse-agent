import {
  averageItemScore,
  bestTimestamp,
  deepDedupeKeys,
  isDigestInstantCandidate,
  isHiddenByDeepDedupe,
  isInstantKind,
  mergeOrphanThemes,
  type DigestView,
  type ThemeGroup,
} from "./digest";
import type { RenderableItem } from "./types";

export interface DigestThemeGroup {
  theme: string;
  item_ids: string[];
}

export interface DigestSnapshotDoc {
  digest_id: string;
  theme_groups?: DigestThemeGroup[];
  summary_item_ids?: string[];
  deep_brief_ids?: string[];
}

export function parseDigestSnapshot(
  raw: Record<string, unknown>,
): DigestSnapshotDoc {
  const themeGroups = Array.isArray(raw.theme_groups)
    ? raw.theme_groups
        .map((g) => {
          const group = g as Record<string, unknown>;
          const theme = typeof group.theme === "string" ? group.theme : "";
          const itemIds = Array.isArray(group.item_ids)
            ? group.item_ids.filter((id): id is string => typeof id === "string")
            : [];
          return { theme, item_ids: itemIds };
        })
        .filter((g) => g.theme && g.item_ids.length > 0)
    : [];

  return {
    digest_id: String(raw.digest_id ?? ""),
    theme_groups: themeGroups,
    summary_item_ids: Array.isArray(raw.summary_item_ids)
      ? raw.summary_item_ids.filter((id): id is string => typeof id === "string")
      : undefined,
    deep_brief_ids: Array.isArray(raw.deep_brief_ids)
      ? raw.deep_brief_ids.filter((id): id is string => typeof id === "string")
      : undefined,
  };
}

/**
 * Merge multiple pipeline digest snapshots (e.g. several runs the same day).
 * Theme order follows first appearance; item order is chronological across runs.
 */
export function mergeDigestSnapshots(
  snapshots: DigestSnapshotDoc[],
): DigestSnapshotDoc | null {
  if (!snapshots.length) return null;

  const themeOrder: string[] = [];
  const seenThemes = new Set<string>();
  const themeItems = new Map<string, string[]>();
  const seenInstant = new Set<string>();
  const deepBriefIds: string[] = [];
  const seenDeep = new Set<string>();

  for (const snap of snapshots) {
    for (const id of snap.deep_brief_ids ?? []) {
      if (!seenDeep.has(id)) {
        seenDeep.add(id);
        deepBriefIds.push(id);
      }
    }
    for (const group of snap.theme_groups ?? []) {
      if (!seenThemes.has(group.theme)) {
        seenThemes.add(group.theme);
        themeOrder.push(group.theme);
      }
      const list = themeItems.get(group.theme) ?? [];
      for (const id of group.item_ids) {
        if (seenInstant.has(id)) continue;
        seenInstant.add(id);
        list.push(id);
      }
      themeItems.set(group.theme, list);
    }
  }

  const theme_groups = themeOrder
    .map((theme) => ({ theme, item_ids: themeItems.get(theme) ?? [] }))
    .filter((g) => g.item_ids.length > 0);

  if (!theme_groups.length && !deepBriefIds.length) return null;

  return {
    digest_id: snapshots[snapshots.length - 1]?.digest_id ?? "merged",
    theme_groups,
    deep_brief_ids: deepBriefIds,
  };
}

/**
 * Today's digest: all delivered items in the pool, with snapshot theme hints
 * merged across runs. Items not referenced by any snapshot still appear
 * (grouped by heuristic themeKey).
 */
export function buildDigestViewForToday(
  items: RenderableItem[],
  snapshots: DigestSnapshotDoc[],
): DigestView {
  const byId = new Map(items.map((item) => [item.id, item]));
  const merged = mergeDigestSnapshots(snapshots);

  const deepInsights = items
    .filter((i) => i.kind === "deep_brief")
    .sort((a, b) => bestTimestamp(b).localeCompare(bestTimestamp(a)));

  const deepKeys = deepDedupeKeys(deepInsights);
  const assigned = new Set(deepInsights.map((d) => d.id));

  const themes: ThemeGroup[] = [];

  for (const group of merged?.theme_groups ?? []) {
    const themeItems = group.item_ids
      .map((id) => byId.get(id))
      .filter((item) => isDigestInstantCandidate(item, deepKeys));
    for (const item of themeItems) assigned.add(item.id);
    if (themeItems.length) themes.push({ theme: group.theme, items: themeItems });
  }

  const orphans = items
    .filter((i) => isInstantKind(i) && i.score > 0 && !assigned.has(i.id))
    .filter((i) => !isHiddenByDeepDedupe(i, deepKeys))
    .sort((a, b) => bestTimestamp(b).localeCompare(bestTimestamp(a)));

  mergeOrphanThemes(themes, orphans);

  const shownInstant = themes.flatMap((t) => t.items);
  return {
    deepInsights,
    themes,
    totalShown: shownInstant.length + deepInsights.length,
    averageScore: averageItemScore(shownInstant),
  };
}

/** Merge today's pipeline snapshots and show all items in the pool. */
export function resolveDigestView(
  items: RenderableItem[],
  snapshots: DigestSnapshotDoc[],
): DigestView {
  return buildDigestViewForToday(items, snapshots);
}
