import { confidenceBadge } from "@/lib/digest";
import type { RenderableItem } from "@/lib/types";

const TONE_STYLES: Record<"good" | "warn" | "bad" | "neutral", string> = {
  good: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:ring-emerald-800",
  warn: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:ring-amber-800",
  bad: "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:ring-rose-800",
  neutral:
    "bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800/40 dark:text-slate-300 dark:ring-slate-700",
};

export function ConfidenceBadge({ item }: { item: RenderableItem }) {
  const { emoji, label, tone } = confidenceBadge(item);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ring-1 ring-inset ${TONE_STYLES[tone]}`}
      title={`score_status=${item.score_status}`}
    >
      <span aria-hidden>{emoji}</span>
      {label}
    </span>
  );
}
