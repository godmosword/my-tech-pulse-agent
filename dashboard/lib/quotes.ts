import "server-only";

/**
 * Shared Finnhub quote fetcher.
 *
 * Returns last price (`c`) and intraday percent change (`dp`) per ticker.
 * Degrades gracefully: no FINNHUB_API_KEY or no tickers → empty Map; a single
 * failed ticker → `{ price: null, changePct: null }`. Callers should batch all
 * tickers in one call and pass quotes down to display components, rather than
 * fetching per-component.
 */
export interface Quote {
  price: number | null;
  changePct: number | null;
}

interface FinnhubQuoteResponse {
  c?: number;
  dp?: number;
}

export async function fetchQuotes(
  tickers: string[],
): Promise<Map<string, Quote>> {
  const out = new Map<string, Quote>();
  const key = process.env.FINNHUB_API_KEY?.trim();

  const unique = Array.from(
    new Set(
      tickers
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean),
    ),
  );
  if (!key || unique.length === 0) return out;

  await Promise.all(
    unique.map(async (ticker) => {
      try {
        const url = new URL("https://finnhub.io/api/v1/quote");
        url.searchParams.set("symbol", ticker);
        url.searchParams.set("token", key);
        const res = await fetch(url.toString(), {
          next: { revalidate: 300 },
        });
        if (!res.ok) {
          out.set(ticker, { price: null, changePct: null });
          return;
        }
        const data = (await res.json()) as FinnhubQuoteResponse;
        const price =
          typeof data.c === "number" && data.c > 0 ? data.c : null;
        const changePct =
          typeof data.dp === "number" && Number.isFinite(data.dp)
            ? data.dp
            : null;
        out.set(ticker, { price, changePct });
      } catch {
        out.set(ticker, { price: null, changePct: null });
      }
    }),
  );

  return out;
}
