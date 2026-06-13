const DASH = "—";

export function fmtNum(
  v: number | null | undefined,
  decimals = 2,
): string {
  if (v == null || !Number.isFinite(v)) return DASH;
  return v.toFixed(decimals);
}

/** Percent without sign (margins, ratios). */
export function fmtPctPlain(
  v: number | null | undefined,
  decimals = 1,
): string {
  if (v == null || !Number.isFinite(v)) return DASH;
  return `${v.toFixed(decimals)}%`;
}

/** Signed percent (returns, deltas). */
export function fmtPctSigned(
  v: number | null | undefined,
  decimals = 2,
): string {
  if (v == null || !Number.isFinite(v)) return DASH;
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(decimals)}%`;
}

/** USD with B/M abbreviation for large magnitudes. */
export function fmtUsd(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
