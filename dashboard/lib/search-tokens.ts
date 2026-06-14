/**
 * Mirror of scoring/search_tokens.py — keep the two in lock-step.
 *
 * The pipeline writes `search_tokens` onto each memory item using the Python
 * implementation; this module reproduces the exact same tokenization for the
 * query side so `array-contains-any` lookups line up token-for-token.
 *
 * Token rules:
 * - Latin/digit runs are lower-cased, split on non-alphanumerics, kept when
 *   length >= 2.
 * - CJK runs become character bigrams (length-1 runs kept as-is).
 */

const LATIN_RE = /[a-z0-9]+/g;
const CJK_RE = /[一-鿿㐀-䶿]+/g;

// Firestore caps `array-contains-any` at 30 disjuncts.
export const QUERY_TOKEN_LIMIT = 30;

function tokensFromText(text: string): Set<string> {
  const out = new Set<string>();
  if (!text) return out;

  const latin = text.toLowerCase().match(LATIN_RE);
  if (latin) {
    for (const word of latin) {
      if (word.length >= 2) out.add(word);
    }
  }

  const cjkRuns = text.match(CJK_RE);
  if (cjkRuns) {
    for (const run of cjkRuns) {
      if (run.length === 1) {
        out.add(run);
        continue;
      }
      for (let i = 0; i < run.length - 1; i += 1) {
        out.add(run.slice(i, i + 2));
      }
    }
  }

  return out;
}

/** Tokenize a raw user query into Firestore `array-contains-any` disjuncts. */
export function tokenizeQuery(query: string, limit = QUERY_TOKEN_LIMIT): string[] {
  return [...tokensFromText((query ?? "").trim())].sort().slice(0, limit);
}

/** Count how many query tokens appear in a document's stored token list. */
export function tokenMatchScore(
  queryTokens: readonly string[],
  docTokens: readonly string[],
): number {
  if (queryTokens.length === 0 || docTokens.length === 0) return 0;
  const set = new Set(docTokens);
  let score = 0;
  for (const token of queryTokens) {
    if (set.has(token)) score += 1;
  }
  return score;
}
