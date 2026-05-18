import type { RenderableItem } from "./types";

const MAX_ENGLISH_EXCERPT = 280;

/** 公開 SEO／OG 用：不輸出完整英文正文。 */
export function englishExcerpt(summary: string, max = MAX_ENGLISH_EXCERPT): string {
  const s = (summary || "").trim().replace(/\s+/g, " ");
  if (!s) return "";
  if (s.length <= max) return s;
  return `${s.slice(0, max - 1)}…`;
}

/**
 * 訪客可見的「摘要」：優先繁中 dek；否則截斷英文。
 * 完整 `summary` 欄仍可能很長，僅在 authenticated 時於 UI 顯示全文。
 */
export function publicSummaryLine(item: RenderableItem): string {
  const zh = item.zh_summary?.trim();
  if (zh) return zh;
  return englishExcerpt(item.summary);
}
