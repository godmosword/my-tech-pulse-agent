import { tokenizeQuery, tokenMatchScore } from "./search-tokens";
import { hasCjk } from "./types";
import type { RenderableItem } from "./types";

/** Build query-side tokens from visible identity fields (fallback when search_tokens missing). */
export function tokensFromRenderable(item: RenderableItem): string[] {
  const set = new Set<string>();
  const fields = [
    item.title,
    item.zh_title,
    item.entity,
    item.hook,
    item.zh_summary,
    item.summary,
  ];
  for (const field of fields) {
    for (const token of tokenizeQuery(field ?? "")) {
      set.add(token);
    }
  }
  for (const ticker of item.tickers ?? []) {
    const key = ticker.trim().toLowerCase();
    if (key) set.add(key);
  }
  return [...set];
}

function searchableHaystack(item: RenderableItem): string {
  return [
    item.title,
    item.zh_title,
    item.entity,
    item.hook,
    item.zh_summary,
    item.summary,
  ]
    .filter(Boolean)
    .join(" ");
}

/** True when query matches item text, tokens, or ticker (bounded-scan fallback). */
export function renderableMatchesQuery(
  item: RenderableItem,
  query: string,
  storedTokens?: string[],
): boolean {
  const q = query.trim();
  if (!q) return false;

  const queryTokens = tokenizeQuery(q);
  const docTokens = storedTokens?.length
    ? storedTokens
    : tokensFromRenderable(item);
  if (queryTokens.length > 0 && tokenMatchScore(queryTokens, docTokens) > 0) {
    return true;
  }

  const hay = searchableHaystack(item);
  if (!hay) return false;

  if (hasCjk(q) && hay.includes(q)) return true;
  if (hay.toLowerCase().includes(q.toLowerCase())) return true;

  const ticker = q.toUpperCase();
  if (/^[A-Z][A-Z0-9.-]{0,5}$/.test(ticker)) {
    return (item.tickers ?? []).some((t) => t.trim().toUpperCase() === ticker);
  }

  return false;
}
