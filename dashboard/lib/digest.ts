import type { RenderableItem } from "./types";

/**
 * Digest selection helpers — TypeScript port of delivery/message_formatter.py.
 *
 * Keep behavior aligned with the Python pipeline so dashboard and Telegram
 * stay in sync. When the algorithm drifts, prefer adding a Firestore snapshot
 * collection (`tech_pulse_digests/<digest_id>`) over rewriting it here twice.
 */

export const HIGH_SCORE_CONFIDENCE_FLOOR = 7.2;

const THEME_KEYWORDS: Record<string, string[]> = {
  "AI 基礎設施": [
    "ai infrastructure",
    "ai chip",
    "ai gpu",
    "ai 算力",
    "ai datacenter",
    "ai cluster",
    "ai accelerator",
    "artificial intelligence",
    "gpu",
    "datacenter",
    "data center",
    "資料中心",
    "nvidia",
    "amd",
    "hbm",
    "tsmc",
    "台積電",
    "tpu",
    "asic",
    "晶片",
    "training cluster",
    "算力",
  ],
  "雲端與企業軟體": [
    "cloud",
    "saas",
    "雲端",
    "azure",
    "aws",
    "gcp",
    "oracle",
    "enterprise",
    "crm",
  ],
  "消費電子": [
    "iphone",
    "android",
    "pc",
    "wearable",
    "consumer",
    "手機",
    "筆電",
    "平板",
    "耳機",
  ],
  "電動車供應鏈": [
    "ev",
    "electric vehicle",
    "battery",
    "tesla",
    "自駕",
    "電動車",
    "車用",
    "充電",
    "鋰電",
  ],
};

const CATEGORY_FALLBACK: Record<string, string> = {
  product_launch: "產品與策略",
  funding: "資本與投資",
  acquisition: "併購與整併",
  regulation: "政策與監管",
  research: "技術研發",
};

export const THEME_EMOJI: Record<string, string> = {
  "AI 基礎設施": "🧠",
  技術研發: "🔬",
  財報焦點: "💰",
  "雲端與企業軟體": "☁️",
  消費電子: "📱",
  "電動車供應鏈": "⚡",
  "資本與投資": "💵",
  "產品與策略": "🚀",
  "政策與監管": "⚖️",
  "併購與整併": "🤝",
  其他焦點: "📡",
};

function containsKeyword(corpus: string, keyword: string): boolean {
  const k = keyword.toLowerCase();
  const hasCJK = /[一-鿿]/.test(k);
  if (hasCJK) return corpus.includes(k);
  const re = new RegExp(`(?<![a-z0-9])${escapeRegex(k)}(?![a-z0-9])`);
  return re.test(corpus);
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function themeKey(item: RenderableItem): string {
  if (item.category === "earnings") return "財報焦點";
  const corpus = `${item.entity} ${item.summary} ${item.title}`.toLowerCase();
  for (const [theme, keywords] of Object.entries(THEME_KEYWORDS)) {
    if (keywords.some((k) => containsKeyword(corpus, k))) return theme;
  }
  return CATEGORY_FALLBACK[item.category] ?? "其他焦點";
}

export interface ThemeGroup {
  theme: string;
  items: RenderableItem[];
}

export interface DigestView {
  deepInsights: RenderableItem[];
  themes: ThemeGroup[];
  totalShown: number;
  averageScore: number;
}

export interface BuildOptions {
  maxThemes?: number;
  maxPerTheme?: number;
  maxTotal?: number;
}

/**
 * Build the single-screen digest view from a freshly loaded snapshot.
 *
 * Mirrors Python's `_format_items_digest_v1` after PR1's dedupe: deep_brief
 * cards are surfaced separately and removed from the instant theme groups so
 * the same headline doesn't appear twice.
 */
export function buildDigest(
  items: RenderableItem[],
  { maxThemes = 4, maxPerTheme = 3, maxTotal = 6 }: BuildOptions = {}
): DigestView {
  const deepInsights = items
    .filter((i) => i.kind === "deep_brief")
    .slice(0, 3);

  const deepKeys = new Set<string>();
  for (const d of deepInsights) {
    if (d.source_url) deepKeys.add(d.source_url.trim());
    if (d.title) deepKeys.add(d.title.trim().toLowerCase());
  }

  const instant = items
    .filter((i) => i.kind === "instant_summary" || i.kind === "earnings")
    .filter((i) => i.score > 0)
    .filter(
      (i) =>
        !deepKeys.has((i.source_url || "").trim()) &&
        !deepKeys.has((i.title || "").trim().toLowerCase())
    )
    .sort((a, b) => b.score - a.score);

  const grouped = new Map<string, RenderableItem[]>();
  for (const item of instant) {
    const key = themeKey(item);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(item);
  }

  const ranked = [...grouped.entries()]
    .map(([theme, list]) => ({
      theme,
      items: list,
      score: themeRankScore(list, maxPerTheme),
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, maxThemes);

  const themes: ThemeGroup[] = [];
  let total = 0;
  for (const { theme, items: list } of ranked) {
    const allowance = Math.min(maxPerTheme, list.length, maxTotal - total);
    if (allowance <= 0) break;
    themes.push({ theme, items: list.slice(0, allowance) });
    total += allowance;
    if (total >= maxTotal) break;
  }

  const shown = themes.flatMap((t) => t.items);
  const avg = shown.length
    ? shown.reduce((acc, x) => acc + x.score, 0) / shown.length
    : 0;

  return {
    deepInsights,
    themes,
    totalShown: shown.length + deepInsights.length,
    averageScore: avg,
  };
}

function themeRankScore(items: RenderableItem[], maxPerTheme: number): number {
  if (!items.length) return 0;
  const avg = items.reduce((a, x) => a + x.score, 0) / items.length;
  const max = Math.max(...items.map((x) => x.score));
  const sizeWeight = Math.min(items.length, maxPerTheme) / maxPerTheme;
  return avg * 0.45 + max * 0.35 + sizeWeight * 10 * 0.2;
}

export function confidenceBadge(item: RenderableItem): {
  emoji: string;
  label: string;
  tone: "good" | "warn" | "bad" | "neutral";
} {
  const status = item.score_status || "ok";
  if (status === "unscored" || status === "fallback") {
    return { emoji: "⚠️", label: "待補驗證", tone: "warn" };
  }
  if (status === "low_score_fallback") {
    return { emoji: "🔴", label: "低信心", tone: "bad" };
  }
  if (status === "high") return { emoji: "✅", label: "高信心", tone: "good" };
  if (status === "medium") return { emoji: "🟡", label: "中信心", tone: "neutral" };
  if (status === "low") {
    if (item.score >= HIGH_SCORE_CONFIDENCE_FLOOR) {
      return { emoji: "🟡", label: "待驗證", tone: "warn" };
    }
    return { emoji: "🔴", label: "低信心", tone: "bad" };
  }
  // `score_status == "ok"` carries no explicit confidence — fall back to score.
  if (item.score >= HIGH_SCORE_CONFIDENCE_FLOOR) {
    return { emoji: "✅", label: "高信心", tone: "good" };
  }
  return { emoji: "🟡", label: "中信心", tone: "neutral" };
}

export function formatScore(score: number): string {
  return score.toFixed(1);
}

export function formatRelativeDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("zh-TW", {
      timeZone: process.env.DIGEST_HEADER_TIMEZONE || "Asia/Taipei",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
