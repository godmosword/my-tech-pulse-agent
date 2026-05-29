import { tagItemPortfolioRelevance } from "@/lib/portfolio-relevance";
import type { RenderableItem } from "@/lib/types";

import { Hairline } from "./Hairline";
import { InstantCard } from "./InstantCard";
import { Kicker } from "./Kicker";
import { NewsTakeawayBlock } from "./NewsTakeawayBlock";

interface Props {
  theme: string;
  items: RenderableItem[];
  authenticated: boolean;
}

/**
 * Editorial section: kicker + serif h2, then theme-grouped InstantCard entries.
 * News takeaway blocks sit below each card when present.
 */
export function ThemeSection({ theme, items, authenticated }: Props) {
  return (
    <section className="pt-10">
      <header className="mb-2 space-y-2">
        <Kicker>Section</Kicker>
        <h2 className="font-serif text-editorial-headline text-ink">
          {theme}
        </h2>
      </header>
      <Hairline />
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
              />
              {item.takeaway && (
                <div className="pb-4">
                  <NewsTakeawayBlock
                    takeaway={item.takeaway}
                    relevance={relevance}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
