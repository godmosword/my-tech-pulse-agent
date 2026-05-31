import { InstantCardNewsList } from "@/components/InstantCardNewsList";
import { isPublicReadMode } from "@/lib/env-public-read";
import { listLatestItems } from "@/lib/firestore";
import { tagItemPortfolioRelevance } from "@/lib/portfolio-relevance";
import { fetchQuotes } from "@/lib/quotes";
import { getReaderSession } from "@/lib/session";

const HOLDING_NEWS_LIMIT = 8;
const LOOKBACK_DAYS = 14;

export async function HoldingNewsSection() {
  const authenticated =
    !isPublicReadMode() || (await getReaderSession()) !== null;
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
        近兩週尚無與您持倉相關的投資短評。新內容會在每日 pipeline 完成後自動出現。
      </p>
    );
  }

  const quotes = await fetchQuotes(
    holdingNews.flatMap((item) => item.tickers ?? []),
  );

  return (
    <InstantCardNewsList
      items={holdingNews}
      authenticated={authenticated}
      quotes={quotes}
      takeawayWrapClassName="pb-3"
    />
  );
}
