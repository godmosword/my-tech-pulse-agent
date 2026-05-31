import fs from "node:fs";
import path from "node:path";

export type BacktestSummary = {
  n_records?: number;
  horizons?: number[];
  by_rating?: Record<string, Record<string, RatingBucket>>;
  quantile_spread?: Record<string, QuantileSpread>;
  ic?: Record<string, { spearman?: number | null; n?: number }>;
  hit_rate?: Record<string, { rate?: number | null; n?: number }>;
  sample_warnings?: Array<{
    horizon_days: number;
    rating: string;
    n: number;
    min_required: number;
  }>;
};

type RatingBucket = {
  n: number;
  mean_excess_pct?: number | null;
  win_rate?: number | null;
  insufficient_sample?: boolean;
};

type QuantileSpread = {
  top_tertile_mean_excess_pct?: number | null;
  bottom_tertile_mean_excess_pct?: number | null;
  spread_pct?: number | null;
  n?: number;
};

export type LiveEvalSummary = {
  n_logged?: number;
  n_evaluated?: number;
  summary?: BacktestSummary;
};

function repoRootFromDashboard(): string {
  return path.resolve(process.cwd(), "..");
}

export function loadBacktestSummary(): BacktestSummary | null {
  const p = path.join(repoRootFromDashboard(), "backtest", "results", "summary.json");
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8")) as BacktestSummary;
  } catch {
    return null;
  }
}

export function loadLiveEvalSummary(): LiveEvalSummary | null {
  const p = path.join(repoRootFromDashboard(), "backtest", "results", "live_eval.json");
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8")) as LiveEvalSummary;
  } catch {
    return null;
  }
}

export function hasInsufficientSample(summary: BacktestSummary | null | undefined): boolean {
  return Boolean(summary?.sample_warnings && summary.sample_warnings.length > 0);
}

/**
 * One-line trust qualifier for signal lists: near-term hit rate at the first
 * available horizon. Returns null when no backtest summary or rate is present
 * so callers can omit the caption entirely.
 */
export function signalHitRateCaption(): string | null {
  const summary = loadBacktestSummary();
  if (!summary) return null;
  const horizons = summary.horizons?.length
    ? summary.horizons
    : Object.keys(summary.hit_rate ?? {}).map(Number);
  const h = horizons[0];
  if (h == null) return null;
  const bucket = summary.hit_rate?.[String(h)];
  if (bucket?.rate == null) return null;
  return `近 ${h} 日訊號命中率 ${(bucket.rate * 100).toFixed(0)}%（n=${bucket.n ?? 0}）`;
}
