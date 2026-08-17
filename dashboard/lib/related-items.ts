import type { RenderableItem } from "./types";

function normalizedTickers(tickers: string[]): Set<string> {
  return new Set(
    tickers
      .map((t) => t.trim().toLowerCase())
      .filter((t) => t.length > 0),
  );
}

function tickerOverlapCount(a: string[], b: string[]): number {
  const setA = normalizedTickers(a);
  let count = 0;
  for (const ticker of normalizedTickers(b)) {
    if (setA.has(ticker)) count += 1;
  }
  return count;
}

function hasSameCategory(current: RenderableItem, candidate: RenderableItem): boolean {
  const left = current.category.trim();
  const right = candidate.category.trim();
  return left.length > 0 && right.length > 0 && left === right;
}

function isCandidateRelated(
  current: RenderableItem,
  candidate: RenderableItem,
): boolean {
  if (candidate.id === current.id) return false;
  if (hasSameCategory(current, candidate)) return true;
  return tickerOverlapCount(current.tickers, candidate.tickers) > 0;
}

/** Pick up to `limit` related items by ticker overlap, then category, then input order. */
export function pickRelatedItems(
  current: RenderableItem,
  candidates: RenderableItem[],
  limit = 2,
): RenderableItem[] {
  const ranked = candidates
    .map((candidate, index) => ({
      candidate,
      index,
      tickerOverlap: tickerOverlapCount(current.tickers, candidate.tickers),
      sameCategory: hasSameCategory(current, candidate),
    }))
    .filter(({ candidate }) => isCandidateRelated(current, candidate))
    .sort((a, b) => {
      if (b.tickerOverlap !== a.tickerOverlap) {
        return b.tickerOverlap - a.tickerOverlap;
      }
      if (a.sameCategory !== b.sameCategory) {
        return Number(b.sameCategory) - Number(a.sameCategory);
      }
      return a.index - b.index;
    });

  return ranked.slice(0, limit).map(({ candidate }) => candidate);
}
