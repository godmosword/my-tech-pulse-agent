import { z } from "zod";

/**
 * Firestore document shape for `tech_pulse_memory_items`.
 *
 * Source of truth: scoring/memory_store.py + docs/PORTAL_CONTRACT.md.
 * We accept Firestore Timestamp objects (with toDate()) or ISO strings — the
 * Admin SDK returns Timestamps; serialized JSON snapshots use strings.
 */
const MemoryItemKindSchema = z.enum([
  "instant_summary",
  "deep_brief",
  "earnings",
]);
export type MemoryItemKind = z.infer<typeof MemoryItemKindSchema>;

const NewsTakeawaySchema = z.object({
  item_id: z.string().optional(),
  takeaway_zh: z.string().default(""),
  angle: z
    .enum([
      "供應鏈",
      "競爭格局",
      "需求訊號",
      "政策監管",
      "技術突破",
      "資本動向",
      "其他",
    ])
    .default("其他"),
  tickers: z.array(z.string()).default([]),
  confidence: z.enum(["high", "medium", "low"]).default("medium"),
});
export type NewsTakeaway = z.infer<typeof NewsTakeawaySchema>;

// P1: position-aware impact (mirrors scoring/portfolio_impact.py PortfolioImpact).
const AffectedPositionSchema = z.object({
  ticker: z.string().default(""),
  kind: z.enum(["direct", "supply_chain", "cluster", "theme"]).default("theme"),
  note_zh: z.string().default(""),
});
const PortfolioImpactSchema = z.object({
  score: z.number().default(0),
  components: z
    .object({
      relevance: z.number().default(0),
      exposure_weight: z.number().default(0),
      relation_weight: z.number().default(0),
      freshness: z.number().default(0),
      confidence: z.number().default(0),
    })
    .nullish(),
  affected_positions: z.array(AffectedPositionSchema).default([]),
  exposure_basis: z.enum(["cost", "market"]).default("cost"),
  rationale_zh: z.string().default(""),
});
export type PortfolioImpact = z.infer<typeof PortfolioImpactSchema>;

const TimestampLikeSchema = z
  .union([
    z.string(),
    z.date(),
    z.object({ toDate: z.function().returns(z.date()) }).passthrough(),
    z.object({ seconds: z.number(), nanoseconds: z.number() }).passthrough(),
  ])
  .nullable()
  .optional();

export const MemoryItemSchema = z.object({
  id: z.string(),
  item_id: z.string().optional(),
  title: z.string().default(""),
  zh_title: z.string().default("").optional(),
  summary: z.string().default(""),
  // Optional Traditional Chinese summary — pipeline started writing it after
  // the bilingual dashboard work. Older docs lack the field; default to "".
  zh_summary: z.string().default("").optional(),
  /** 完整繁中譯文（舊文件可能缺）。 */
  zh_body: z.string().default("").optional(),
  source_url: z.string().default(""),
  source_name: z.string().default(""),
  entity: z.string().default(""),
  category: z.string().default(""),
  kind: MemoryItemKindSchema.default("instant_summary"),
  score: z.number().default(0),
  score_status: z.string().default("ok"),
  hook: z.string().default("").optional(),
  tickers: z.array(z.string()).default([]).optional(),
  what_happened: z.string().default("").optional(),
  why_it_matters: z.string().default("").optional(),
  takeaway: NewsTakeawaySchema.nullish(),
  portfolio_impact: PortfolioImpactSchema.nullish(),
  published_at: TimestampLikeSchema,
  delivered_at: TimestampLikeSchema,
});

/** Normalized item ready for rendering: timestamps coerced to ISO strings. */
export interface RenderableItem {
  id: string;
  title: string;
  zh_title: string;
  summary: string;
  zh_summary: string;
  zh_body: string;
  source_url: string;
  source_name: string;
  entity: string;
  category: string;
  kind: MemoryItemKind;
  score: number;
  score_status: string;
  hook: string;
  tickers: string[];
  what_happened: string;
  why_it_matters: string;
  takeaway: NewsTakeaway | null;
  portfolio_impact: PortfolioImpact | null;
  published_at_iso: string | null;
  delivered_at_iso: string | null;
  themes: string[];
}

/**
 * Reader-facing priority badge for an article card.
 * Thresholds match scoring/scorer.py expectations:
 *   ≥ 8.0 → HIGH   (red dot)
 *   ≥ 5.0 → MED    (amber dot)
 *   < 5.0 → LOW    (neutral dot)
 */
export type PriorityLevel = "high" | "med" | "low";

export function priorityLevel(score: number): PriorityLevel {
  if (score >= 8.0) return "high";
  if (score >= 5.0) return "med";
  return "low";
}

export const PRIORITY_LABEL: Record<PriorityLevel, string> = {
  high: "🔴 HIGH",
  med: "🟡 MED",
  low: "⚪ LOW",
};

/** Tailwind dot color per priority level. */
export const PRIORITY_DOT_CLASS: Record<PriorityLevel, string> = {
  high: "bg-red-500",
  med: "bg-amber-500",
  low: "bg-ink-faint",
};

const ZH_TITLE_MIN_CHARS = 8;
const ZH_TITLE_SHORT_MAX = 12;
const CJK_RE = /[\u4e00-\u9fff\u3400-\u4dbf]/;

/** 含漢字才視為可用繁中標題／摘要（排除僅 OpenCC 轉換的英文 fallback）。 */
export function hasCjk(text: string): boolean {
  return CJK_RE.test(text);
}

function normalizeComparable(value: string): string {
  return value.trim().toLowerCase();
}

/** 取繁中摘要的第一句，作為缺 zh_title 時的標題 fallback。 */
function firstZhSentence(text: string): string {
  const t = text.trim();
  if (!t) return "";
  const match = t.match(/^[^。！？.!?]+[。！？.!?]?/u);
  return (match?.[0] ?? t).trim();
}

/** 品質過低的 zh_title 不應蓋過完整的 title。 */
function isWeakZhTitle(
  zhTitle: string,
  options: { title?: string; entity?: string } = {},
): boolean {
  const zh = zhTitle.trim();
  if (!zh) return true;
  if (zh.length < ZH_TITLE_MIN_CHARS) return true;

  const entity = options.entity?.trim();
  if (entity && normalizeComparable(zh) === normalizeComparable(entity)) {
    return true;
  }

  const title = options.title?.trim();
  if (
    zh.length < ZH_TITLE_SHORT_MAX &&
    title &&
    title.length >= zh.length * 2
  ) {
    return true;
  }

  return false;
}

function zhHeadlineCandidate(
  text: string,
  options: { title?: string; entity?: string },
): string | null {
  const trimmed = text.trim();
  if (!trimmed || !hasCjk(trimmed)) return null;
  const fromText = firstZhSentence(trimmed);
  if (
    fromText.length >= ZH_TITLE_MIN_CHARS &&
    !isWeakZhTitle(fromText, options)
  ) {
    return fromText;
  }
  return null;
}

/** 顯示用標題：優先 zh_title，其次 hook／zh_summary／zh_body 首句，最後英文 title。 */
export function displayTitle(item: {
  zh_title?: string;
  hook?: string;
  zh_summary?: string;
  zh_body?: string;
  title?: string;
  entity?: string;
}): string {
  const title = item.title?.trim();
  const entity = item.entity?.trim();
  const weakOpts = { title, entity };

  const zh = item.zh_title?.trim();
  if (zh && !isWeakZhTitle(zh, weakOpts)) {
    return zh;
  }

  for (const source of [
    item.hook,
    item.zh_summary,
    item.zh_body,
  ]) {
    const candidate = zhHeadlineCandidate(source ?? "", weakOpts);
    if (candidate) return candidate;
  }

  return title || entity || "Untitled";
}

/**
 * 列表副標：完整 zh_summary；若標題已取自首句則只顯示剩餘段落，避免重複。
 */
export function listingZhSubline(item: {
  zh_title?: string;
  hook?: string;
  zh_summary?: string;
  zh_body?: string;
  title?: string;
  entity?: string;
}): string | null {
  const summary = item.zh_summary?.trim();
  if (!summary || !hasCjk(summary)) return null;

  const headline = displayTitle(item);
  const first = firstZhSentence(summary);
  if (headline === summary) return null;
  if (headline === first) {
    const rest = summary.slice(first.length).trim();
    return rest || null;
  }
  return summary;
}

export function toIsoString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value || null;
  if (typeof value === "object") {
    const maybe = value as { toDate?: () => Date; seconds?: number };
    if (typeof maybe.toDate === "function") {
      try {
        return maybe.toDate().toISOString();
      } catch {
        return null;
      }
    }
    if (typeof maybe.seconds === "number") {
      return new Date(maybe.seconds * 1000).toISOString();
    }
  }
  return null;
}
