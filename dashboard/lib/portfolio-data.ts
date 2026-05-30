import portfolioJson from "./portfolio-data.json";

export interface PositionRow {
  ticker: string;
  shares: number;
  avgCost: number | null;
}

export type TargetAllocation = Record<string, number>;

interface PortfolioJson {
  base_currency: string;
  as_of: string;
  positions: Array<{
    ticker: string;
    shares: number;
    avg_cost: number | null;
  }>;
  target_allocation: TargetAllocation;
}

const DATA = portfolioJson as PortfolioJson;

export function loadPortfolio(): {
  positions: PositionRow[];
  target: TargetAllocation;
  asOf: string;
  baseCurrency: string;
} {
  return {
    positions: (DATA.positions ?? []).map((p) => ({
      ticker: p.ticker.toUpperCase(),
      shares: Number(p.shares),
      avgCost: p.avg_cost != null ? Number(p.avg_cost) : null,
    })),
    target: DATA.target_allocation ?? {},
    asOf: DATA.as_of ?? "",
    baseCurrency: DATA.base_currency ?? "USD",
  };
}

export function holdingsTickerSet(): Set<string> {
  return new Set(loadPortfolio().positions.map((p) => p.ticker));
}
