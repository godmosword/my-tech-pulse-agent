import type { Quote } from "@/lib/quotes";

interface TickerQuoteProps {
  ticker: string;
  /** Batched by the server parent; omit / null → renders the bare ticker. */
  quote?: Quote | null;
}

function fmtPrice(price: number): string {
  return `$${price.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function fmtChange(changePct: number): string {
  const sign = changePct > 0 ? "+" : "";
  return `${sign}${changePct.toFixed(1)}%`;
}

/**
 * Ticker chip, optionally annotated with last price and intraday change.
 * Editorial restraint: mono numerals, pos/neg color only on the change.
 * Degrades to the plain bordered ticker chip when no quote is available, so
 * pages without FINNHUB_API_KEY look exactly as before.
 */
export function TickerQuote({ ticker, quote }: TickerQuoteProps) {
  const price = quote?.price ?? null;
  const changePct = quote?.changePct ?? null;
  const changeClass =
    changePct == null
      ? ""
      : changePct > 0
        ? "text-pos"
        : changePct < 0
          ? "text-neg"
          : "text-ink-faint";

  return (
    <span className="inline-flex items-center gap-1.5 rounded-sm border border-rule px-1.5 py-0.5 font-mono text-kicker text-ink">
      <span>{ticker}</span>
      {price != null && (
        <span className="text-ink-soft">{fmtPrice(price)}</span>
      )}
      {changePct != null && (
        <span className={changeClass}>{fmtChange(changePct)}</span>
      )}
    </span>
  );
}
