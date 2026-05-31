import { tagItemPortfolioRelevance } from "@/lib/portfolio-relevance";
import type { Quote } from "@/lib/quotes";
import type { RenderableItem } from "@/lib/types";

import { InstantCard } from "./InstantCard";
import { NewsTakeawayBlock } from "./NewsTakeawayBlock";

type Props = {
  items: RenderableItem[];
  authenticated: boolean;
  quotes: Map<string, Quote>;
  /** Wrapper around NewsTakeawayBlock — preserves per-page spacing. */
  takeawayWrapClassName?: string;
};

/** Shared InstantCard + optional NewsTakeawayBlock list for editorial feeds. */
export function InstantCardNewsList({
  items,
  authenticated,
  quotes,
  takeawayWrapClassName = "pb-4",
}: Props) {
  return (
    <ul className="divide-y divide-rule">
      {items.map((item) => {
        const returnToPath = `/item/${encodeURIComponent(item.id)}`;
        const relevance = item.takeaway
          ? tagItemPortfolioRelevance(item.takeaway.tickers)
          : tagItemPortfolioRelevance(item.tickers);
        return (
          <li key={item.id}>
            <InstantCard
              item={item}
              authenticated={authenticated}
              returnToPath={returnToPath}
              variant="list"
              quotes={quotes}
            />
            {item.takeaway && (
              <div className={takeawayWrapClassName}>
                <NewsTakeawayBlock takeaway={item.takeaway} relevance={relevance} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
