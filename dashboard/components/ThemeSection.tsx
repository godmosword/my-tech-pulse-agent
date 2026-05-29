import Link from "next/link";

import { displayTitle, listingZhSubline, type RenderableItem } from "@/lib/types";
import { tagItemPortfolioRelevance } from "@/lib/portfolio-relevance";
import { bestTimestamp, formatRelativeDateline } from "@/lib/digest";

import { Hairline } from "./Hairline";
import { Kicker, MetaDot } from "./Kicker";
import { NewsTakeawayBlock } from "./NewsTakeawayBlock";

interface Props {
  theme: string;
  items: RenderableItem[];
  authenticated: boolean;
}

/**
 * Editorial section: kicker + serif h2, then a bilingual title list.
 * Each row shows source/date kicker, a Chinese headline, and (when present)
 * the remainder of zh_summary underneath. Tapping the
 * headline goes to the item detail page for the full read.
 */
export function ThemeSection({ theme, items }: Props) {
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
          const subline = listingZhSubline(item);
          const relevance = item.takeaway
            ? tagItemPortfolioRelevance(item.takeaway.tickers)
            : tagItemPortfolioRelevance(item.tickers);
          return (
          <li key={item.id} className="py-4">
            <Link
              href={`/item/${encodeURIComponent(item.id)}`}
              className="block space-y-2 hover:[&_h3]:underline"
            >
              <Kicker as="div" className="flex flex-wrap items-center">
                {item.source_name && <span>{item.source_name}</span>}
                {formatRelativeDateline(bestTimestamp(item)) && (
                  <>
                    {item.source_name && <MetaDot />}
                    <span className="tabular-nums">
                      {formatRelativeDateline(bestTimestamp(item))}
                    </span>
                  </>
                )}
              </Kicker>
              <h3 className="font-serif text-editorial-headline text-ink">
                {displayTitle(item)}
              </h3>
              {subline && (
                <p className="font-sans text-editorial-body leading-snug text-ink-soft">
                  {subline}
                </p>
              )}
              {item.takeaway && (
                <NewsTakeawayBlock takeaway={item.takeaway} relevance={relevance} />
              )}
            </Link>
          </li>
          );
        })}
      </ul>
    </section>
  );
}
