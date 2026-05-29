import type { NewsTakeaway } from "@/lib/types";
import type { PortfolioRelevanceResult } from "@/lib/portfolio-relevance";

const ANGLE_CLASS =
  "inline-block rounded border border-rule bg-paper px-1.5 py-0.5 font-sans text-kicker uppercase tracking-wide text-ink-faint";

interface NewsTakeawayBlockProps {
  takeaway: NewsTakeaway;
  relevance?: PortfolioRelevanceResult;
}

export function NewsTakeawayBlock({ takeaway, relevance }: NewsTakeawayBlockProps) {
  const zh = takeaway.takeaway_zh?.trim();
  if (!zh) return null;

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className={ANGLE_CLASS}>{takeaway.angle}</span>
        {relevance?.relevance === "holding" && (
          <span className="inline-block rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 font-sans text-kicker text-accent">
            持倉相關 · {relevance.matched.join(", ")}
          </span>
        )}
        {relevance?.relevance === "watchlist" && (
          <span className="inline-block rounded border border-rule bg-paper-tint px-1.5 py-0.5 font-sans text-kicker text-ink-soft">
            觀察清單 · {relevance.matched.join(", ")}
          </span>
        )}
      </div>
      <p className="font-sans text-meta leading-snug text-ink-soft">{zh}</p>
    </div>
  );
}
