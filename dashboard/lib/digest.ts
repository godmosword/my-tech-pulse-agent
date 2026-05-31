import type { RenderableItem } from "./types";

/**
 * Digest selection helpers — TypeScript port of delivery/message_formatter.py.
 *
 * Keep behavior aligned with the Python pipeline so dashboard and Telegram
 * stay in sync. When the algorithm drifts, prefer adding a Firestore snapshot
 * collection (`tech_pulse_digests/<digest_id>`) over rewriting it here twice.
 */

const HIGH_SCORE_CONFIDENCE_FLOOR = 7.2;

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

function themeKey(item: RenderableItem): string {
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

export function isInstantKind(item: RenderableItem): boolean {
  return item.kind === "instant_summary" || item.kind === "earnings";
}

/** URL/title keys used to hide instant rows that duplicate a deep brief. */
export function deepDedupeKeys(deepInsights: RenderableItem[]): Set<string> {
  const keys = new Set<string>();
  for (const d of deepInsights) {
    if (d.source_url) keys.add(d.source_url.trim());
    if (d.title) keys.add(d.title.trim().toLowerCase());
  }
  return keys;
}

export function isHiddenByDeepDedupe(
  item: RenderableItem,
  deepKeys: Set<string>,
): boolean {
  return (
    deepKeys.has((item.source_url || "").trim()) ||
    deepKeys.has((item.title || "").trim().toLowerCase())
  );
}

export function isDigestInstantCandidate(
  item: RenderableItem | undefined,
  deepKeys: Set<string>,
): item is RenderableItem {
  if (!item) return false;
  if (!isInstantKind(item)) return false;
  if (item.score <= 0) return false;
  return !isHiddenByDeepDedupe(item, deepKeys);
}

export function averageItemScore(items: RenderableItem[]): number {
  if (!items.length) return 0;
  return items.reduce((acc, x) => acc + x.score, 0) / items.length;
}

/** Attach orphan instant items to snapshot theme groups (mutates `themes`). */
export function mergeOrphanThemes(
  themes: ThemeGroup[],
  orphans: RenderableItem[],
): void {
  const orphanByTheme = new Map<string, RenderableItem[]>();
  for (const item of orphans) {
    const key = themeKey(item);
    if (!orphanByTheme.has(key)) orphanByTheme.set(key, []);
    orphanByTheme.get(key)!.push(item);
  }

  const existingThemes = new Set(themes.map((t) => t.theme));
  const orphanThemes = [...orphanByTheme.entries()]
    .map(([theme, list]) => ({
      theme,
      items: list,
      latestIso: list.reduce((acc, x) => {
        const ts = bestTimestamp(x);
        return ts && ts > acc ? ts : acc;
      }, ""),
    }))
    .sort((a, b) => b.latestIso.localeCompare(a.latestIso));

  for (const { theme, items: list } of orphanThemes) {
    if (existingThemes.has(theme)) {
      themes.find((t) => t.theme === theme)?.items.push(...list);
    } else {
      themes.push({ theme, items: list });
    }
  }
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
