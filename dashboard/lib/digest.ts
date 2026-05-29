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
    .sort((a, b) => bestTimestamp(b).localeCompare(bestTimestamp(a)))
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
    // Time-first: sort by the same timestamp the UI displays
    // (published_at preferred, delivered_at fallback) so reader-visible time
    // is monotonic and never contradicts the running order.
    .sort((a, b) => bestTimestamp(b).localeCompare(bestTimestamp(a)));

  const grouped = new Map<string, RenderableItem[]>();
  for (const item of instant) {
    const key = themeKey(item);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(item);
  }

  const ranked = [...grouped.entries()]
    .map(([theme, list]) => ({
      theme,
      // Items already in DESC delivered_at order from the parent sort.
      items: list,
      // Use the freshest visible timestamp as the theme's sort key so the most
      // recently updated section surfaces first.
      latestIso: list.reduce((acc, x) => {
        const ts = bestTimestamp(x);
        return ts && ts > acc ? ts : acc;
      }, ""),
    }))
    .sort((a, b) => b.latestIso.localeCompare(a.latestIso))
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


export function confidenceBadge(item: RenderableItem): {
  /** Editorial label, used by ConfidenceBadge component (text-only). */
  label: string;
  /** Drives whether the badge picks up the accent color. */
  tone: "good" | "warn" | "bad" | "neutral";
} {
  const status = item.score_status || "ok";
  if (status === "unscored" || status === "fallback") {
    return { label: "Unverified", tone: "warn" };
  }
  if (status === "low_score_fallback") {
    return { label: "Low confidence", tone: "bad" };
  }
  if (status === "high") return { label: "High confidence", tone: "good" };
  if (status === "medium") return { label: "Medium confidence", tone: "neutral" };
  if (status === "low") {
    if (item.score >= HIGH_SCORE_CONFIDENCE_FLOOR) {
      return { label: "Provisional", tone: "warn" };
    }
    return { label: "Low confidence", tone: "bad" };
  }
  // `score_status == "ok"` carries no explicit confidence — fall back to score.
  if (item.score >= HIGH_SCORE_CONFIDENCE_FLOOR) {
    return { label: "High confidence", tone: "good" };
  }
  return { label: "Medium confidence", tone: "neutral" };
}

/** Show confidence badge only when editorial attention is warranted. */
export function shouldShowConfidenceBadge(item: RenderableItem): boolean {
  const { tone } = confidenceBadge(item);
  return tone === "warn" || tone === "bad";
}

export function formatScore(score: number): string {
  return score.toFixed(1);
}

const TIMEZONE = process.env.DIGEST_HEADER_TIMEZONE || "Asia/Taipei";

/**
 * Long editorial date: "MAY 17, 2026". Masthead + archive day headers.
 */
export function formatEditorialDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso)
      .toLocaleDateString("en-US", {
        timeZone: TIMEZONE,
        month: "long",
        day: "numeric",
        year: "numeric",
      })
      .toUpperCase();
  } catch {
    return iso;
  }
}

/**
 * The timestamp the reader sees. Prefer the article's own published_at; fall
 * back to delivered_at. Returns "" when both are missing so localeCompare
 * still works in sort.
 */
export function bestTimestamp(item: {
  published_at_iso: string | null;
  delivered_at_iso: string | null;
}): string {
  return item.published_at_iso || item.delivered_at_iso || "";
}

/**
 * Reader-facing time stamp:
 *   <60s          → 剛剛
 *   <60min        → N 分鐘前
 *   same day TPE  → 今天 HH:MM
 *   yesterday     → 昨日 HH:MM
 *   else          → MAY 17 · 11:15
 *
 * Keeps the editorial fixed-date format for older items so the page reads
 * like a newspaper, but adds a "fresh" cue for items in the last day.
 */
export function formatRelativeDateline(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "";
  let d: Date;
  try {
    d = new Date(iso);
  } catch {
    return iso;
  }
  const diffMs = now.getTime() - d.getTime();
  if (diffMs < 0) return formatMetaDate(iso);
  if (diffMs < 60_000) return "剛剛";
  if (diffMs < 60 * 60_000) {
    return `${Math.floor(diffMs / 60_000)} 分鐘前`;
  }
  const dayKey = (x: Date) =>
    x.toLocaleDateString("en-CA", { timeZone: TIMEZONE });
  const today = dayKey(now);
  const yesterday = dayKey(new Date(now.getTime() - 24 * 60 * 60_000));
  const key = dayKey(d);
  const hhmm = d.toLocaleTimeString("en-GB", {
    timeZone: TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
  });
  if (key === today) return `今天 ${hhmm}`;
  if (key === yesterday) return `昨日 ${hhmm}`;
  return formatMetaDate(iso);
}

/** Compact meta: "MAY 17 · 11:15" for inline kicker meta lines. */
export function formatMetaDate(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const day = d
      .toLocaleDateString("en-US", {
        timeZone: TIMEZONE,
        month: "short",
        day: "numeric",
      })
      .toUpperCase();
    const time = d.toLocaleTimeString("en-GB", {
      timeZone: TIMEZONE,
      hour: "2-digit",
      minute: "2-digit",
    });
    return `${day} · ${time}`;
  } catch {
    return iso;
  }
}

/** Legacy zh-TW format — kept available but no longer used in editorial UI. */
export function formatRelativeDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("zh-TW", {
      timeZone: TIMEZONE,
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

// Maps raw extractor categories (used across instant / deep / earnings kinds)
// to editorial section labels rendered in kickers. Unknown values fall back
// to a title-cased version so nothing silently disappears.
const CATEGORY_LABELS: Record<string, string> = {
  product_launch: "產品發布",
  funding: "融資",
  acquisition: "併購",
  earnings: "財報",
  regulation: "監管",
  research: "研究分析",
  other: "即時快訊",
  ai: "AI",
  semiconductor: "半導體",
  crypto: "加密貨幣",
};

export function categoryLabel(category: string): string {
  const key = (category || "").toLowerCase();
  if (!key) return "Dispatch";
  return CATEGORY_LABELS[key] ?? category.replace(/_/g, " ");
}
