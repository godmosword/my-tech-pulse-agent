import type { RenderableItem } from "./types";

import { englishExcerpt, publicSummaryLine } from "./public-excerpt";

/** 登入後主文：優先完整繁中譯本，舊稿 fallback 英文 summary。 */
export function authenticatedPrimaryBody(item: RenderableItem): string {
  const zh = item.zh_body?.trim();
  if (zh) return zh;
  return (item.summary || "").trim();
}

export function hasGatedLongContent(item: RenderableItem): boolean {
  if (item.zh_body?.trim()) {
    return true;
  }
  const s = item.summary?.trim();
  if (!s) return false;
  return (
    s.length > englishExcerpt(s).length ||
    (Boolean(item.zh_summary?.trim()) && Boolean(s))
  );
}
