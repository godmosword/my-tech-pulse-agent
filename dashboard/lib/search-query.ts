import { z } from "zod";

const TICKER_RE = /^[A-Z][A-Z0-9.-]{0,5}$/;

export const SearchQuerySchema = z.object({
  q: z.string().trim().min(1, "query_required").max(80, "query_too_long"),
});

export interface NormalizedSearchQuery {
  /** Trimmed user input. */
  q: string;
  /** Uppercased ticker when input looks like a symbol. */
  ticker: string | null;
  isTickerLike: boolean;
}

export function normalizeSearchQuery(raw: string): NormalizedSearchQuery {
  const q = raw.trim();
  const upper = q.toUpperCase();
  const isTickerLike = TICKER_RE.test(upper);
  return {
    q,
    ticker: isTickerLike ? upper : null,
    isTickerLike,
  };
}

/** ASCII title prefix variants for case-insensitive prefix match. */
export function titlePrefixBounds(q: string): string[] {
  const trimmed = q.trim();
  if (!trimmed) return [];
  const variants = new Set<string>([trimmed]);
  const lower = trimmed.toLowerCase();
  const upper = trimmed.toUpperCase();
  const title =
    lower.charAt(0).toUpperCase() + lower.slice(1);
  variants.add(lower);
  variants.add(upper);
  variants.add(title);
  return [...variants];
}
