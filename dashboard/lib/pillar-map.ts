import watchlistData from "./earnings-watchlist-data.json";

/** Q-Silicon `api_routers/earnings.py` PILLAR_BY_TICKER (subset). */
export const PILLAR_BY_TICKER: Record<string, string> = {
  MSFT: "cloud_software",
  GOOGL: "cloud_software",
  META: "cloud_software",
  AMZN: "cloud_software",
  ORCL: "cloud_software",
  CRM: "cloud_software",
  NOW: "cloud_software",
  SNOW: "cloud_software",
  PLTR: "cloud_software",
  CRWD: "cloud_software",
  NET: "cloud_software",
  NVDA: "ai_silicon",
  AMD: "ai_silicon",
  AVGO: "ai_silicon",
  MRVL: "ai_silicon",
  QCOM: "ai_silicon",
  ARM: "ai_silicon",
  TSM: "semiconductor",
  INTC: "semiconductor",
  MU: "semiconductor",
  SMCI: "hardware",
  DELL: "hardware",
  HPE: "hardware",
  ANET: "hardware",
  CSCO: "hardware",
  LITE: "optical",
  COHR: "optical",
  FN: "optical",
  AAPL: "consumer_devices",
};

export interface WatchlistEntryRow {
  ticker: string;
  tier: number | null;
  tags: string[];
}

const WATCHLIST: WatchlistEntryRow[] = (
  watchlistData as { entries: WatchlistEntryRow[] }
).entries.map((e) => ({
  ticker: e.ticker.toUpperCase(),
  tier: e.tier ?? null,
  tags: e.tags ?? [],
}));

export function pillarFor(symbol: string): string {
  const sym = symbol.toUpperCase();
  if (PILLAR_BY_TICKER[sym]) return PILLAR_BY_TICKER[sym];
  const entry = WATCHLIST.find((e) => e.ticker === sym);
  if (entry?.tags?.[0]) return entry.tags[0];
  return "other";
}

export function watchlistTickerSet(): Set<string> {
  return new Set(WATCHLIST.map((e) => e.ticker));
}
