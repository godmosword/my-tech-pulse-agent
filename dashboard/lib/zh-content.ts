import { displayTitle, type RenderableItem } from "./types";

import { englishExcerpt } from "./public-excerpt";

/** 內文頁「中文摘要」：導讀 +（若有）完整繁中正文，去重後合併。 */
export function chineseAbstract(item: RenderableItem): string {
  const parts: string[] = [];
  const summary = item.zh_summary?.trim();
  if (summary) parts.push(summary);
  const body = item.zh_body?.trim();
  if (body && body !== summary && !(summary && summary.includes(body))) {
    parts.push(body);
  }
  return parts.join("\n\n");
}

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

/** 與顯示用中文標題不同的英文原題；相同則不重複。 */
export function bilingualEnglishTitle(item: RenderableItem): string | null {
  const en = item.title?.trim();
  if (!en) return null;
  return en === displayTitle(item) ? null : en;
}

export function bilingualEnglishSummary(item: RenderableItem): string | null {
  return item.summary?.trim() || null;
}

/** 有任一中文欄且有可對照的英文標題／摘要時顯示。不必等 zh_body。 */
export function shouldShowBilingualCompare(item: RenderableItem): boolean {
  const hasZh = Boolean(
    item.zh_title?.trim() || item.zh_summary?.trim() || item.zh_body?.trim(),
  );
  const enTitle = bilingualEnglishTitle(item);
  const enSummary = bilingualEnglishSummary(item);
  return Boolean(hasZh && (enTitle || enSummary));
}
