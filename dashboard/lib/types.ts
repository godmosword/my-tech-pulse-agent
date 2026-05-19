import { z } from "zod";

/**
 * Firestore document shape for `tech_pulse_memory_items`.
 *
 * Source of truth: scoring/memory_store.py + docs/PORTAL_CONTRACT.md.
 * We accept Firestore Timestamp objects (with toDate()) or ISO strings — the
 * Admin SDK returns Timestamps; serialized JSON snapshots use strings.
 */
export const MemoryItemKindSchema = z.enum([
  "instant_summary",
  "deep_brief",
  "earnings",
]);
export type MemoryItemKind = z.infer<typeof MemoryItemKindSchema>;

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
  tickers: z.array(z.string()).default([]).optional(),
  what_happened: z.string().default("").optional(),
  why_it_matters: z.string().default("").optional(),
  published_at: TimestampLikeSchema,
  delivered_at: TimestampLikeSchema,
});
export type MemoryItem = z.infer<typeof MemoryItemSchema>;

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
  tickers: string[];
  what_happened: string;
  why_it_matters: string;
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

function normalizeComparable(value: string): string {
  return value.trim().toLowerCase();
}

/** 品質過低的 zh_title 不應蓋過完整的 title。 */
export function isWeakZhTitle(
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

/** 顯示用標題：優先 zh_title（繁中），其次 LLM 給的 title，最後 entity。 */
export function displayTitle(item: {
  zh_title?: string;
  title?: string;
  entity?: string;
}): string {
  const zh = item.zh_title?.trim();
  const title = item.title?.trim();
  const entity = item.entity?.trim();

  if (zh && !isWeakZhTitle(zh, { title, entity })) {
    return zh;
  }
  return title || entity || "Untitled";
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
