import "server-only";

import { displayTitle, hasCjk, type RenderableItem } from "./types";
import { collectionName, getItemById, listLatestItems } from "./firestore";

/** Aligned with investment-ai-agent `api_routers/news.py` PILLAR_ALIASES. */
export const PILLAR_ALIASES: Record<string, string[]> = {
  ai: [
    "ai",
    "人工智慧",
    "artificial intelligence",
    "openai",
    "gemini",
    "llm",
  ],
  semiconductor: [
    "semiconductor",
    "semiconductors",
    "semis",
    "semi",
    "chip",
    "chips",
    "hbm",
    "半導體",
    "先進封裝",
  ],
  crypto: [
    "crypto",
    "cryptocurrency",
    "bitcoin",
    "btc",
    "ethereum",
    "eth",
    "加密",
    "區塊鏈",
  ],
};

export type NewsPillar = keyof typeof PILLAR_ALIASES;

export interface NewsThemeCount {
  id: string;
  label: string;
  count: number;
}

export interface NewsDigestItem {
  id: string;
  title: string;
  headline: string;
  summary: string;
  gemini_take: string;
  commentary_zh: string;
  commentary_en: string;
  source_domain: string;
  source_url: string;
  published_at: string;
  date: string;
  tags: string[];
  pillar: string;
  pillar_key: string;
  confidence: number | null;
}

export interface NewsDeepItem extends NewsDigestItem {
  deep_brief: string;
  body: string;
  content: string;
  thesis_breakdown: string[];
  tickers: string[];
  reading_minutes: number;
}

function firstText(
  data: Record<string, unknown>,
  keys: string[],
): string {
  for (const key of keys) {
    const value = data[key];
    if (value == null) continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return "";
}

function asList(value: unknown): string[] {
  if (value == null) return [];
  const raw =
    Array.isArray(value) || value instanceof Set
      ? [...(value as Iterable<string>)]
      : String(value).split(/[,/|]/);
  const items: string[] = [];
  for (const item of raw) {
    const text = String(item).trim();
    if (text && !items.includes(text)) items.push(text);
  }
  return items;
}

function sourceDomain(sourceUrl: string, sourceName: string): string {
  let hostname = "";
  if (sourceUrl) {
    try {
      hostname = new URL(sourceUrl).hostname.toLowerCase();
    } catch {
      hostname = "";
    }
  }
  let domain = (hostname || sourceName).trim().toLowerCase();
  if (domain.startsWith("www.")) domain = domain.slice(4);
  return domain;
}

export function normalizePillar(value: string | null | undefined): NewsPillar | "" {
  const text = (value || "").trim().toLowerCase();
  if (!text) return "";
  for (const [canonical, aliases] of Object.entries(PILLAR_ALIASES)) {
    if (text === canonical || aliases.some((a) => a.toLowerCase() === text)) {
      return canonical as NewsPillar;
    }
  }
  return "";
}

function textHasAlias(haystack: string, alias: string): boolean {
  const needle = alias.toLowerCase();
  if (!needle) return false;
  if (/^[a-z0-9]+$/.test(needle)) {
    return new RegExp(`\\b${needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(
      haystack,
    );
  }
  return haystack.includes(needle);
}

export function estimateReadingMinutes(text: string): number {
  const t = text.trim();
  if (!t) return 0;
  const wordCount = (t.match(/[A-Za-z0-9]+/g) || []).length;
  const cjkCount = (t.match(/[\u4e00-\u9fff]/g) || []).length;
  const minutes = Math.max(wordCount / 220, cjkCount / 500);
  return Math.max(1, Math.ceil(minutes));
}

export function inferPillarKey(opts: {
  pillar?: string;
  theme?: string;
  tags?: string[];
  headline?: string;
  take?: string;
  deepText?: string;
}): NewsPillar | "" {
  for (const value of [
    opts.pillar,
    opts.theme,
    ...(opts.tags || []),
  ]) {
    const normalized = normalizePillar(value);
    if (normalized) return normalized;
  }
  const haystack = [
    opts.headline,
    opts.take,
    opts.deepText,
    ...(opts.tags || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  for (const [canonical, aliases] of Object.entries(PILLAR_ALIASES)) {
    if (aliases.some((alias) => textHasAlias(haystack, alias))) {
      return canonical as NewsPillar;
    }
  }
  return "";
}

function isoDatePart(iso: string | null): string {
  if (!iso) return "";
  return iso.slice(0, 10);
}

function matchesDateFilter(itemDate: string, publishedIso: string | null, filter: string): boolean {
  if (!filter) return true;
  const pub = isoDatePart(publishedIso);
  return itemDate === filter || pub === filter || (publishedIso || "").startsWith(filter);
}

function englishTake(item: RenderableItem): string {
  return (
    item.summary?.trim() ||
    [item.what_happened, item.why_it_matters].filter(Boolean).join(" ").trim()
  );
}

function commentaryZh(item: RenderableItem, take: string): string {
  const zs = item.zh_summary?.trim();
  if (zs && hasCjk(zs)) return zs;
  const hook = item.hook?.trim();
  if (hook && hasCjk(hook)) return hook;
  const title = displayTitle(item);
  if (title && hasCjk(title) && title !== item.title) return title;
  return take;
}

/** Map Firestore memory item → Q-Silicon Portal news contract. */
export function normalizeNewsItem(
  item: RenderableItem,
  options: { includeDeep?: boolean; raw?: Record<string, unknown> } = {},
): NewsDigestItem | NewsDeepItem | null {
  const raw = options.raw || {};
  const headline = displayTitle(item);
  const take = englishTake(item);
  const sourceUrl = item.source_url?.trim() || firstText(raw, ["source_url", "url", "link"]);
  const sourceName = item.source_name?.trim() || firstText(raw, ["source_name", "publisher"]);
  const domain = sourceDomain(sourceUrl, sourceName);
  if (!item.id || !headline || !domain) return null;

  const publishedAt = item.published_at_iso || item.delivered_at_iso || "";
  const tags = asList(raw.tags ?? raw.topics ?? raw.categories);
  const pillarLabel = firstText(raw, ["pillar", "theme", "primary_theme"]) || item.category;
  if (pillarLabel && !tags.includes(pillarLabel)) tags.push(pillarLabel);

  const pillarKey = inferPillarKey({
    pillar: pillarLabel,
    tags,
    headline,
    take: commentaryZh(item, take),
    deepText: options.includeDeep ? item.zh_body || item.summary : "",
  });

  const score = item.score;
  const confidence =
    typeof score === "number" && Number.isFinite(score) ? score : null;

  const base: NewsDigestItem = {
    id: item.id,
    title: headline,
    headline,
    summary: take,
    gemini_take: take,
    commentary_zh: commentaryZh(item, take),
    commentary_en: firstText(raw, ["commentary_en", "take_en", "summary_en"]),
    source_domain: domain,
    source_url: sourceUrl,
    published_at: publishedAt,
    date: isoDatePart(publishedAt) || isoDatePart(item.delivered_at_iso),
    tags,
    pillar: pillarLabel,
    pillar_key: pillarKey,
    confidence,
  };

  if (!options.includeDeep) return base;

  const deepText =
    item.zh_body?.trim() ||
    (item.kind === "deep_brief" ? item.summary?.trim() : "") ||
    firstText(raw, ["deep_brief", "brief", "analysis", "body", "content"]);
  const thesis = asList(raw.thesis_breakdown ?? raw.thesis ?? raw.bullets);
  const tickers =
    item.tickers?.length > 0 ? item.tickers : asList(raw.tickers ?? raw.symbols);

  return {
    ...base,
    deep_brief: deepText,
    body: deepText,
    content: deepText,
    thesis_breakdown: thesis,
    tickers,
    reading_minutes: estimateReadingMinutes(deepText || take),
    pillar_key:
      inferPillarKey({
        pillar: pillarLabel,
        tags,
        headline,
        take: base.commentary_zh,
        deepText,
      }) || pillarKey,
  };
}

function sortKey(item: NewsDigestItem): string {
  return item.published_at || item.date || "";
}

export function themeCounts(
  items: NewsDigestItem[],
  limit = 12,
): NewsThemeCount[] {
  const counts = new Map<string, { label: string; count: number }>();
  for (const item of items) {
    for (const tag of item.tags) {
      const label = tag.trim();
      if (!label) continue;
      const key = label.toLowerCase();
      const prev = counts.get(key);
      counts.set(key, {
        label: prev?.label ?? label,
        count: (prev?.count ?? 0) + 1,
      });
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, limit)
    .map(([key, { label, count }]) => ({
      id: label.replace(/[^0-9A-Za-z\u4e00-\u9fff]+/g, "-").replace(/^-|-$/g, ""),
      label,
      count,
    }));
}

function hasDeepContent(item: NewsDeepItem | NewsDigestItem, kind: string): boolean {
  const deep = item as NewsDeepItem;
  return Boolean(
    deep.deep_brief?.trim() ||
      deep.body?.trim() ||
      deep.content?.trim() ||
      kind === "deep_brief",
  );
}

function matchesPillar(item: NewsDigestItem, pillar: NewsPillar | ""): boolean {
  if (!pillar) return true;
  if (item.pillar_key === pillar) return true;
  if (item.tags.some((t) => normalizePillar(t) === pillar)) return true;
  const haystack = [
    item.headline,
    item.gemini_take,
    (item as NewsDeepItem).deep_brief,
    (item as NewsDeepItem).body,
    item.pillar,
    ...item.tags,
  ]
    .join(" ")
    .toLowerCase();
  return PILLAR_ALIASES[pillar].some((alias) => textHasAlias(haystack, alias));
}

async function fetchRecentItems(scanLimit: number): Promise<RenderableItem[]> {
  return listLatestItems({ limit: Math.min(Math.max(scanLimit, 20), 250) });
}

export async function loadNewsDigestItems(
  limit: number,
  dateFilter?: string | null,
): Promise<NewsDigestItem[]> {
  const scan = Math.max(limit * 3, limit);
  const rows = await fetchRecentItems(scan);
  const items: NewsDigestItem[] = [];
  for (const row of rows) {
    const normalized = normalizeNewsItem(row);
    if (!normalized) continue;
    if (!matchesDateFilter(normalized.date, row.published_at_iso, dateFilter || "")) {
      continue;
    }
    if (row.kind === "earnings") continue;
    items.push(normalized);
  }
  return items
    .sort((a, b) => sortKey(b).localeCompare(sortKey(a)))
    .slice(0, limit);
}

export async function loadNewsDeepItems(
  limit: number,
  pillar?: string | null,
): Promise<NewsDeepItem[]> {
  const canonical = normalizePillar(pillar);
  const scan = Math.min(Math.max(limit * 5, 80), 250);
  const rows = await fetchRecentItems(scan);
  const items: NewsDeepItem[] = [];
  for (const row of rows) {
    if (row.kind !== "deep_brief" && !row.zh_body?.trim()) continue;
    const normalized = normalizeNewsItem(row, { includeDeep: true });
    if (!normalized || !("deep_brief" in normalized)) continue;
    const deep = normalized as NewsDeepItem;
    if (!hasDeepContent(deep, row.kind)) continue;
    if (!matchesPillar(deep, canonical)) continue;
    items.push(deep);
  }
  return items
    .sort((a, b) => sortKey(b).localeCompare(sortKey(a)))
    .slice(0, limit);
}

export async function getNewsDeepById(itemId: string): Promise<NewsDeepItem | null> {
  const ident = itemId.trim();
  if (!ident) return null;
  const direct = await getItemById(ident);
  if (direct) {
    const normalized = normalizeNewsItem(direct, { includeDeep: true });
    if (normalized && "deep_brief" in normalized) return normalized as NewsDeepItem;
  }
  const scan = await loadNewsDeepItems(100, null);
  return scan.find((i) => i.id === ident) ?? null;
}

/** Plain-text block for investment-ai-agent `TECH_PULSE_URL` / `summary` JSON field. */
export function buildNewsExclusionSummary(items: NewsDigestItem[], maxLines = 8): string {
  const lines = items.slice(0, maxLines).map((item) => {
    const lead = item.commentary_zh?.trim() || item.headline;
    const src = item.source_domain ? `（${item.source_domain}）` : "";
    return `• ${lead}${src}`;
  });
  return lines.join("\n").trim();
}

export function newsSourceLabel(): string {
  return `firestore:${collectionName()}`;
}
