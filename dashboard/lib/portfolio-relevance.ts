/** Portfolio relevance for news takeaway tickers (server-side). */

import { holdingsTickerSet } from "./portfolio-data";
import { watchlistTickerSet } from "./pillar-map";

export type PortfolioRelevance = "holding" | "watchlist" | "none";

export interface PortfolioRelevanceResult {
  relevance: PortfolioRelevance;
  matched: string[];
}

export function tagItemPortfolioRelevance(
  tickers: string[] | undefined | null,
  holdings: Set<string> = holdingsTickerSet(),
  watchlist: Set<string> = watchlistTickerSet(),
): PortfolioRelevanceResult {
  const normalized = (tickers ?? [])
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);
  const matchedHoldings = normalized.filter((t) => holdings.has(t));
  if (matchedHoldings.length > 0) {
    return { relevance: "holding", matched: matchedHoldings };
  }
  const matchedWatch = normalized.filter((t) => watchlist.has(t));
  if (matchedWatch.length > 0) {
    return { relevance: "watchlist", matched: matchedWatch };
  }
  return { relevance: "none", matched: [] };
}
