import { buildDigest, type DigestView } from "./digest";
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

/**
 * Build homepage digest view from a pipeline-written Firestore snapshot.
 * Falls back to null when snapshot is incomplete or items are missing.
 */
export function buildDigestViewFromSnapshot(
  snapshot: DigestSnapshotDoc,
  items: RenderableItem[],
): DigestView | null {
  const byId = new Map(items.map((item) => [item.id, item]));
  const groups = snapshot.theme_groups ?? [];
  if (!groups.length) return null;

  const deepIds = new Set(snapshot.deep_brief_ids ?? []);
  const deepInsights = (snapshot.deep_brief_ids ?? [])
    .map((id) => byId.get(id))
    .filter((item): item is RenderableItem => Boolean(item));

  const themes: DigestView["themes"] = [];
  let totalShown = deepInsights.length;

  for (const group of groups) {
    const themeItems = group.item_ids
      .map((id) => byId.get(id))
      .filter((item): item is RenderableItem => {
        if (!item) return false;
        if (deepIds.has(item.id)) return false;
        return item.kind === "instant_summary" || item.kind === "earnings";
      });
    if (!themeItems.length) continue;
    themes.push({ theme: group.theme, items: themeItems });
    totalShown += themeItems.length;
  }

  if (!themes.length && !deepInsights.length) return null;

  const shownInstant = themes.flatMap((t) => t.items);
  const avg = shownInstant.length
    ? shownInstant.reduce((acc, x) => acc + x.score, 0) / shownInstant.length
    : 0;

  return {
    deepInsights,
    themes,
    totalShown,
    averageScore: avg,
  };
}

/** Prefer snapshot when present; otherwise compute from items. */
export function resolveDigestView(
  items: RenderableItem[],
  snapshot: DigestSnapshotDoc | null,
): DigestView {
  if (snapshot) {
    const fromSnapshot = buildDigestViewFromSnapshot(snapshot, items);
    if (fromSnapshot) return fromSnapshot;
  }
  return buildDigest(items);
}
