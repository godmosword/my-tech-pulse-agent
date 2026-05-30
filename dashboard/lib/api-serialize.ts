import type { RenderableItem } from "./types";
import { displayTitle } from "./types";
import { englishExcerpt, publicSummaryLine } from "./public-excerpt";
import type { ApiAccess } from "./api-auth";
import type { DigestView } from "./digest";

export interface ApiItem {
  id: string;
  title_en: string;
  title_zh: string;
  summary_zh: string | null;
  summary_en: string | null;
  category: string;
  kind: string;
  entity: string;
  source_name: string;
  source_url: string;
  tickers: string[];
  score: number;
  score_status: string;
  published_at: string | null;
  delivered_at: string | null;
  zh_body?: string | null;
  hook?: string | null;
}

export function serializeItem(
  item: RenderableItem,
  access: ApiAccess,
): ApiItem {
  const titleZh = displayTitle(item);
  const base: ApiItem = {
    id: item.id,
    title_en: item.title,
    title_zh: titleZh,
    summary_zh: null,
    summary_en: null,
    category: item.category,
    kind: item.kind,
    entity: item.entity,
    source_name: item.source_name,
    source_url: item.source_url,
    tickers: item.tickers ?? [],
    score: item.score,
    score_status: item.score_status,
    published_at: item.published_at_iso,
    delivered_at: item.delivered_at_iso,
  };

  if (access.full) {
    return {
      ...base,
      summary_zh: item.zh_summary?.trim() || null,
      summary_en: item.summary?.trim() || null,
      zh_body: item.zh_body?.trim() || null,
      hook: item.hook?.trim() || null,
    };
  }

  const publicZh = item.zh_summary?.trim() || publicSummaryLine(item) || null;
  return {
    ...base,
    summary_zh: publicZh,
    summary_en: item.summary?.trim()
      ? englishExcerpt(item.summary)
      : null,
  };
}

export function serializeDigest(
  view: DigestView,
  access: ApiAccess,
): {
  deep_insights: ApiItem[];
  themes: Array<{ theme: string; items: ApiItem[] }>;
  total_shown: number;
  average_score: number;
} {
  return {
    deep_insights: view.deepInsights.map((i) => serializeItem(i, access)),
    themes: view.themes.map((t) => ({
      theme: t.theme,
      items: t.items.map((i) => serializeItem(i, access)),
    })),
    total_shown: view.totalShown,
    average_score: view.averageScore,
  };
}
