import { fetchQuotes } from "@/lib/quotes";
import type { RenderableItem } from "@/lib/types";

import { Hairline } from "./Hairline";
import { InstantCardNewsList } from "./InstantCardNewsList";
import { Kicker } from "./Kicker";

interface Props {
  theme: string;
  items: RenderableItem[];
  authenticated: boolean;
}

/**
 * Editorial section: kicker + serif h2, then theme-grouped InstantCard entries.
 * News takeaway blocks sit below each card when present.
 */
export async function ThemeSection({ theme, items, authenticated }: Props) {
  const quotes = await fetchQuotes(items.flatMap((item) => item.tickers ?? []));
  return (
    <section className="pt-10">
      <header className="mb-2 space-y-2">
        <Kicker>主題</Kicker>
        <h2 className="font-serif text-headline text-ink">
          {theme}
        </h2>
      </header>
      <Hairline />
      <InstantCardNewsList
        items={items}
        authenticated={authenticated}
        quotes={quotes}
        takeawayWrapClassName="pb-4"
      />
    </section>
  );
}
