import Link from "next/link";

import { signalHitRateCaption } from "@/lib/backtest-data";
import { listEarningsSince } from "@/lib/earnings-firestore";
import { loadUpcomingEarnings } from "@/lib/earnings-portal";
import { listLatestItems } from "@/lib/firestore";
import {
  tagItemPortfolioRelevance,
  type PortfolioRelevance,
} from "@/lib/portfolio-relevance";
import { fetchQuotes, type Quote } from "@/lib/quotes";
import { displayTitle, type RenderableItem } from "@/lib/types";

import { Hairline } from "./Hairline";
import { Kicker } from "./Kicker";
import { RatingBadge } from "./data/RatingBadge";
import { TickerQuote } from "./data/TickerQuote";

const HOLDING_NEWS_LOOKBACK_MS = 48 * 60 * 60 * 1000;
const SIGNAL_LOOKBACK_DAYS = 30;
const BUY_THRESHOLD = 60;
const AVOID_THRESHOLD = 45;

/** holding > watchlist > none, so "my book" items float to the top. */
const RELEVANCE_RANK: Record<PortfolioRelevance, number> = {
  holding: 0,
  watchlist: 1,
  none: 2,
};

interface HoldingNewsRow {
  id: string;
  title: string;
  takeaway_zh: string;
  angle: string;
  tickers: string[];
}

interface SignalRow {
  report_id: string;
  ticker: string;
  quarter_label: string;
  score: number;
  rating: string;
  conviction: string;
  relevance: PortfolioRelevance;
}

interface UpcomingRow {
  ticker: string;
  date: string;
  days_until: number;
  pillar: string;
}

function holdingNewsRows(items: RenderableItem[]): HoldingNewsRow[] {
  return items
    .filter((item) => {
      const tickers = item.takeaway?.tickers;
      if (!item.takeaway?.takeaway_zh?.trim() || !tickers?.length) return false;
      return tagItemPortfolioRelevance(tickers).relevance === "holding";
    })
    .slice(0, 4)
    .map((item) => ({
      id: item.id,
      title: displayTitle(item),
      takeaway_zh: item.takeaway?.takeaway_zh?.trim() ?? "",
      angle: item.takeaway?.angle ?? "",
      tickers: tagItemPortfolioRelevance(item.takeaway?.tickers).matched,
    }));
}

function signalRows(
  reports: Awaited<ReturnType<typeof listEarningsSince>>,
): { buys: SignalRow[]; avoids: SignalRow[] } {
  const scored: SignalRow[] = reports
    .filter((r) => r.investment_signal?.score != null)
    .map((r) => {
      const sig = r.investment_signal!;
      return {
        report_id: r.report_id,
        ticker: r.ticker,
        quarter_label: r.quarter_label,
        score: sig.score as number,
        rating: sig.rating,
        conviction: sig.conviction,
        relevance: tagItemPortfolioRelevance([r.ticker]).relevance,
      };
    });

  const byRelevanceThen = (dir: "desc" | "asc") => (a: SignalRow, b: SignalRow) => {
    const rank = RELEVANCE_RANK[a.relevance] - RELEVANCE_RANK[b.relevance];
    if (rank !== 0) return rank;
    return dir === "desc" ? b.score - a.score : a.score - b.score;
  };

  const buys = scored
    .filter((s) => s.score >= BUY_THRESHOLD)
    .sort(byRelevanceThen("desc"))
    .slice(0, 3);
  const avoids = scored
    .filter((s) => s.score < AVOID_THRESHOLD)
    .sort(byRelevanceThen("asc"))
    .slice(0, 3);

  return { buys, avoids };
}

function SubLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 mt-5 font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-faint first:mt-0">
      {children}
    </p>
  );
}

export async function AttentionTriage() {
  const since48 = new Date(Date.now() - HOLDING_NEWS_LOOKBACK_MS);
  const since30 = new Date();
  since30.setUTCDate(since30.getUTCDate() - SIGNAL_LOOKBACK_DAYS);

  const [recentItems, reports, upcoming] = await Promise.all([
    listLatestItems({ limit: 120, since: since48 }).catch(() => [] as RenderableItem[]),
    listEarningsSince(since30, { limit: 80, maxTier: 5 }).catch(() => []),
    loadUpcomingEarnings(7).catch(() => null),
  ]);

  const holdingNews = holdingNewsRows(recentItems);
  const { buys, avoids } = signalRows(reports);
  const upcomingRows: UpcomingRow[] = (upcoming?.items ?? [])
    .slice(0, 5)
    .map((item) => ({
      ticker: item.symbol,
      date: item.next_earnings_date,
      days_until: item.days_until,
      pillar: item.pillar,
    }));

  const hasContent =
    holdingNews.length > 0 ||
    buys.length > 0 ||
    avoids.length > 0 ||
    upcomingRows.length > 0;

  // Batch all quotes for the section in a single Finnhub pass.
  const allTickers = [
    ...holdingNews.flatMap((r) => r.tickers),
    ...buys.map((r) => r.ticker),
    ...avoids.map((r) => r.ticker),
    ...upcomingRows.map((r) => r.ticker),
  ];
  const quotes: Map<string, Quote> = hasContent
    ? await fetchQuotes(allTickers)
    : new Map();

  const trustCaption = signalHitRateCaption();

  return (
    <section className="pt-4">
      <Kicker tone="accent">需要關注</Kicker>
      <Hairline className="mt-3" />

      {!hasContent ? (
        <p className="py-6 font-sans text-body text-ink-soft">
          目前無需立即關注的事項。持倉新聞、跨門檻訊號與近期財報會在每日 pipeline
          完成後自動出現於此。{" "}
          <Link
            href="/invest"
            className="text-accent underline-offset-4 hover:underline"
          >
            前往投資中樞 →
          </Link>
        </p>
      ) : (
        <div className="pt-3">
          {holdingNews.length > 0 && (
            <div>
              <SubLabel>持倉重大新聞</SubLabel>
              <ul className="divide-y divide-rule">
                {holdingNews.map((row) => (
                  <li key={row.id} className="py-3">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <Link
                        href={`/item/${encodeURIComponent(row.id)}`}
                        className="font-serif text-lg text-ink hover:text-accent hover:underline"
                      >
                        {row.title}
                      </Link>
                      {row.angle && (
                        <span className="font-sans text-kicker uppercase tracking-[0.12em] text-ink-faint">
                          {row.angle}
                        </span>
                      )}
                    </div>
                    {row.takeaway_zh && (
                      <p className="mt-1 font-sans text-body text-ink-soft line-clamp-1">
                        {row.takeaway_zh}
                      </p>
                    )}
                    {row.tickers.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {row.tickers.map((t) => (
                          <TickerQuote key={t} ticker={t} quote={quotes.get(t)} />
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(buys.length > 0 || avoids.length > 0) && (
            <div>
              <SubLabel>訊號跨越門檻</SubLabel>
              <ul className="divide-y divide-rule">
                {[...buys, ...avoids].map((row) => (
                  <li
                    key={row.report_id}
                    className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <TickerQuote ticker={row.ticker} quote={quotes.get(row.ticker)} />
                      <Link
                        href={`/earnings/report/${encodeURIComponent(row.report_id)}`}
                        className="font-sans text-meta text-ink-soft hover:text-accent hover:underline"
                      >
                        {row.quarter_label}
                      </Link>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-meta text-ink">
                        {row.score.toFixed(1)}
                      </span>
                      <RatingBadge rating={row.rating} conviction={row.conviction} />
                    </div>
                  </li>
                ))}
              </ul>
              {trustCaption && (
                <p className="mt-2 font-sans text-kicker uppercase tracking-[0.1em] text-ink-faint">
                  {trustCaption}
                </p>
              )}
            </div>
          )}

          {upcomingRows.length > 0 && (
            <div>
              <SubLabel>未來 7 日財報</SubLabel>
              <ul className="divide-y divide-rule">
                {upcomingRows.map((row) => (
                  <li
                    key={`${row.ticker}-${row.date}`}
                    className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3"
                  >
                    <TickerQuote ticker={row.ticker} quote={quotes.get(row.ticker)} />
                    <span className="font-sans text-meta text-ink-soft">
                      {row.date} · {row.days_until} 日後 · {row.pillar}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
