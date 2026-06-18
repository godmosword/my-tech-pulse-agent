import type { PortfolioTier } from "@/lib/portfolio-metrics";

/**
 * Small badge marking whether a ticker is in the book (持倉) or watched (觀察).
 * Returns null for "other" so non-portfolio rows stay unmarked. Shared by the
 * signals table and the home earnings list so the label/styling stay consistent.
 */
export function PortfolioTierBadge({ tier }: { tier: PortfolioTier }) {
  if (tier === "holding") {
    return (
      <span className="rounded bg-accent/15 px-1.5 py-0.5 font-sans text-meta text-accent">
        持倉
      </span>
    );
  }
  if (tier === "watchlist") {
    return (
      <span className="rounded border border-rule px-1.5 py-0.5 font-sans text-meta text-ink-faint">
        觀察
      </span>
    );
  }
  return null;
}
