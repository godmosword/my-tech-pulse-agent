import Link from "next/link";

import { NewsTakeawayBlock } from "@/components/NewsTakeawayBlock";
import { listLatestItems } from "@/lib/firestore";
import { tagItemPortfolioRelevance } from "@/lib/portfolio-relevance";
import { displayTitle } from "@/lib/types";

const HOLDING_NEWS_LIMIT = 8;
const LOOKBACK_DAYS = 14;

export async function HoldingNewsSection() {
  const since = new Date(Date.now() - LOOKBACK_DAYS * 24 * 60 * 60 * 1000);
  const items = await listLatestItems({ limit: 120, since });

  const holdingNews = items
    .filter((item) => {
      const tickers = item.takeaway?.tickers;
      if (!item.takeaway?.takeaway_zh?.trim() || !tickers?.length) return false;
      return tagItemPortfolioRelevance(tickers).relevance === "holding";
    })
    .slice(0, HOLDING_NEWS_LIMIT);

  if (holdingNews.length === 0) {
    return (
      <p className="font-sans text-body text-ink-soft">
        近期尚無與持倉相關的投資短評（需 pipeline 開啟{" "}
        <code className="text-meta">NEWS_TAKEAWAY_MODE=on</code> 且新聞含 takeaway）。
      </p>
    );
  }

  return (
    <ul className="divide-y divide-rule">
      {holdingNews.map((item) => {
        const relevance = tagItemPortfolioRelevance(item.takeaway?.tickers);
        return (
          <li key={item.id} className="py-3 first:pt-0">
            <Link
              href={`/item/${encodeURIComponent(item.id)}`}
              className="block space-y-1 hover:[&_h3]:underline"
            >
              <h3 className="font-serif text-editorial-body font-medium text-ink">
                {displayTitle(item)}
              </h3>
              {item.takeaway && (
                <NewsTakeawayBlock takeaway={item.takeaway} relevance={relevance} />
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
