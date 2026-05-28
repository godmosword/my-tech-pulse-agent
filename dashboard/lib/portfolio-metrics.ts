/**
 * Pure portfolio valuation / tier / exposure helpers (no server-only imports).
 */

import { pillarFor } from "./pillar-map";

export type PortfolioTier = "holding" | "watchlist" | "other";

const TAG_TO_ALLOCATION_THEME: Record<string, string> = {
  ai_infra: "ai_silicon",
  ai_silicon: "ai_silicon",
  semiconductor: "semiconductor",
  memory: "memory",
  hbm: "memory",
  equipment: "equipment",
  cloud_software: "cloud_software",
};

export function normalizeTheme(raw: string): string {
  const key = raw.trim().toLowerCase();
  return TAG_TO_ALLOCATION_THEME[key] ?? key;
}

export function themeForTicker(ticker: string): string {
  return normalizeTheme(pillarFor(ticker));
}

export function classifyTier(
  ticker: string,
  holdingsSet: Set<string>,
  watchlistSet: Set<string>,
): PortfolioTier {
  const sym = ticker.toUpperCase();
  if (holdingsSet.has(sym)) return "holding";
  if (watchlistSet.has(sym)) return "watchlist";
  return "other";
}

export interface PositionInput {
  ticker: string;
  shares: number;
  avgCost: number | null;
}

export interface ValuedPosition {
  ticker: string;
  shares: number;
  avgCost: number | null;
  price: number | null;
  marketValue: number;
  usedCostBasis: boolean;
}

export function valuePositions(
  positions: PositionInput[],
  prices: Map<string, number | null>,
): { rows: ValuedPosition[]; priced: boolean } {
  let priced = Boolean(prices.size);
  const rows: ValuedPosition[] = positions.map((p) => {
    const sym = p.ticker.toUpperCase();
    const quote = prices.get(sym);
    const hasQuote = quote != null && quote > 0;
    const costBasis =
      p.avgCost != null && p.avgCost > 0 ? p.avgCost * p.shares : null;
    const marketValue = hasQuote ? quote! * p.shares : costBasis ?? 0;
    if (!hasQuote) priced = false;
    return {
      ticker: sym,
      shares: p.shares,
      avgCost: p.avgCost,
      price: hasQuote ? quote! : null,
      marketValue,
      usedCostBasis: !hasQuote,
    };
  });
  return { rows, priced };
}

export interface ThemeExposureRow {
  theme: string;
  marketValue: number;
  weightPct: number;
}

export function themeExposure(
  valued: ValuedPosition[],
  themeFor: (ticker: string) => string,
): ThemeExposureRow[] {
  const total = valued.reduce((s, p) => s + p.marketValue, 0);
  if (total <= 0) return [];
  const byTheme = new Map<string, number>();
  for (const p of valued) {
    const theme = themeFor(p.ticker);
    byTheme.set(theme, (byTheme.get(theme) ?? 0) + p.marketValue);
  }
  return [...byTheme.entries()]
    .map(([theme, marketValue]) => ({
      theme,
      marketValue,
      weightPct: round2((marketValue / total) * 100),
    }))
    .sort((a, b) => b.marketValue - a.marketValue);
}

export interface AllocationDriftRow {
  theme: string;
  currentPct: number;
  targetPct: number;
  driftPct: number;
}

export function allocationDrift(
  exposure: ThemeExposureRow[],
  target: Record<string, number>,
): AllocationDriftRow[] {
  const themes = new Set([
    ...exposure.map((e) => e.theme),
    ...Object.keys(target),
  ]);
  const exposureMap = new Map(exposure.map((e) => [e.theme, e.weightPct]));
  const rows: AllocationDriftRow[] = [];
  for (const theme of themes) {
    const currentPct = exposureMap.get(theme) ?? 0;
    const targetPct = round2((target[theme] ?? 0) * 100);
    rows.push({
      theme,
      currentPct,
      targetPct,
      driftPct: round2(currentPct - targetPct),
    });
  }
  return rows.sort(
    (a, b) => Math.abs(b.driftPct) - Math.abs(a.driftPct) || a.theme.localeCompare(b.theme),
  );
}

export function concentrationMetrics(
  valued: ValuedPosition[],
  exposure: ThemeExposureRow[],
): { top_position_pct: number; top_theme_pct: number } {
  const total = valued.reduce((s, p) => s + p.marketValue, 0);
  const topPos =
    total > 0
      ? Math.max(...valued.map((p) => (p.marketValue / total) * 100), 0)
      : 0;
  const topTheme = exposure.length ? exposure[0].weightPct : 0;
  return {
    top_position_pct: round2(topPos),
    top_theme_pct: round2(topTheme),
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function attachPortfolioTier<T extends { ticker: string }>(
  items: T[],
  holdingsSet: Set<string>,
  watchlistSet: Set<string>,
): Array<T & { portfolio_tier: PortfolioTier }> {
  return items.map((item) => ({
    ...item,
    portfolio_tier: classifyTier(item.ticker, holdingsSet, watchlistSet),
  }));
}
