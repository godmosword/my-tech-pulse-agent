import { confidenceBadge, shouldShowConfidenceBadge } from "@/lib/digest";
import type { RenderableItem } from "@/lib/types";

/**
 * Editorial confidence badge: small caps text, no emoji, no pill background.
 * Tone only changes the color — "bad" picks up the oxblood accent so failed
 * confidence stands out; everything else reads as plain meta.
 */
export function ConfidenceBadge({ item }: { item: RenderableItem }) {
  if (!shouldShowConfidenceBadge(item)) return null;

  const { label, tone } = confidenceBadge(item);
  const toneClass =
    tone === "bad"
      ? "text-accent"
      : tone === "warn"
        ? "text-ink"
        : "text-ink-soft";
  return (
    <span
      className={`font-sans text-kicker font-semibold uppercase tracking-[0.12em] ${toneClass}`}
      aria-label={`信心標記：${label}`}
      title={`score_status=${item.score_status}`}
    >
      {label}
    </span>
  );
}
