import "server-only";

import { holdingsTickerSet, loadPortfolio } from "./portfolio-data";
import {
  allocationDrift,
  attachPortfolioTier,
  classifyTier,
  concentrationMetrics,
  themeExposure,
  themeForTicker,
  valuePositions,
  type AllocationDriftRow,
  type PortfolioTier,
  type ThemeExposureRow,
} from "./portfolio-metrics";
import { watchlistTickerSet } from "./pillar-map";

export type { PortfolioTier };

export interface PortfolioPositionRow {
  ticker: string;
  shares: number;
  avg_cost: number | null;
  price: number | null;
  market_value: number;
  weight_pct: number;
  theme: string;
  tier: PortfolioTier;
  unrealized_pct: number | null;
}

export interface PortfolioApiPayload {
  as_of: string;
  total_market_value: number;
  priced: boolean;
  positions: PortfolioPositionRow[];
  theme_exposure: ThemeExposureRow[];
  allocation_drift: AllocationDriftRow[];
  concentration: { top_position_pct: number; top_theme_pct: number };
  source: string;
}

async function fetchFinnhubQuotes(
  tickers: string[],
): Promise<Map<string, number | null>> {
  const key = process.env.FINNHUB_API_KEY?.trim();
  const out = new Map<string, number | null>();
  if (!key || !tickers.length) return out;

  await Promise.all(
    tickers.map(async (ticker) => {
      try {
        const url = new URL("https://finnhub.io/api/v1/quote");
        url.searchParams.set("symbol", ticker);
        url.searchParams.set("token", key);
        const res = await fetch(url.toString(), { next: { revalidate: 300 } });
        if (!res.ok) {
          out.set(ticker, null);
          return;
        }
        const data = (await res.json()) as { c?: number };
        const c = typeof data.c === "number" && data.c > 0 ? data.c : null;
        out.set(ticker, c);
      } catch {
        out.set(ticker, null);
      }
    }),
  );
  return out;
}

export async function buildPortfolioPayload(): Promise<PortfolioApiPayload> {
  const { positions, target, asOf } = loadPortfolio();
  const tickers = positions.map((p) => p.ticker);
  const quotes = await fetchFinnhubQuotes(tickers);
  const { rows: valued, priced } = valuePositions(
    positions.map((p) => ({
      ticker: p.ticker,
      shares: p.shares,
      avgCost: p.avgCost,
    })),
    quotes,
  );

  const total = valued.reduce((s, p) => s + p.marketValue, 0);
  const holdingsSet = holdingsTickerSet();
  const watchlistSet = watchlistTickerSet();

  const positionRows: PortfolioPositionRow[] = valued.map((p) => {
    const weight_pct = total > 0 ? Math.round((p.marketValue / total) * 10000) / 100 : 0;
    let unrealized_pct: number | null = null;
    if (p.price != null && p.avgCost != null && p.avgCost > 0) {
      unrealized_pct = Math.round(((p.price - p.avgCost) / p.avgCost) * 10000) / 100;
    }
    return {
      ticker: p.ticker,
      shares: p.shares,
      avg_cost: p.avgCost,
      price: p.price,
      market_value: Math.round(p.marketValue * 100) / 100,
      weight_pct,
      theme: themeForTicker(p.ticker),
      tier: classifyTier(p.ticker, holdingsSet, watchlistSet),
      unrealized_pct,
    };
  });

  const exposure = themeExposure(valued, themeForTicker);
  const drift = allocationDrift(exposure, target);
  const concentration = concentrationMetrics(valued, exposure);

  return {
    as_of: asOf,
    total_market_value: Math.round(total * 100) / 100,
    priced,
    positions: positionRows.sort((a, b) => b.market_value - a.market_value),
    theme_exposure: exposure,
    allocation_drift: drift,
    concentration,
    source: "config/portfolio.yaml",
  };
}

export function getPortfolioTierSets(): {
  holdingsSet: Set<string>;
  watchlistSet: Set<string>;
} {
  return {
    holdingsSet: holdingsTickerSet(),
    watchlistSet: watchlistTickerSet(),
  };
}

export function withPortfolioTierOnReports<T extends { ticker: string }>(
  items: T[],
): Array<T & { portfolio_tier: PortfolioTier }> {
  const { holdingsSet, watchlistSet } = getPortfolioTierSets();
  return attachPortfolioTier(items, holdingsSet, watchlistSet);
}

export function withPortfolioTierOnSymbols<T extends { symbol: string }>(
  items: T[],
): Array<T & { portfolio_tier: PortfolioTier }> {
  const { holdingsSet, watchlistSet } = getPortfolioTierSets();
  return items.map((item) => ({
    ...item,
    portfolio_tier: classifyTier(item.symbol, holdingsSet, watchlistSet),
  }));
}
