import "server-only";

import { getFirestore } from "firebase-admin/firestore";

import { listEarningsReports } from "./earnings-firestore";
import { getApp, listLatestItems } from "./firestore";
import {
  normalizeSearchQuery,
  titlePrefixBounds,
  type NormalizedSearchQuery,
} from "./search-query";
import { tokenizeQuery, tokenMatchScore } from "./search-tokens";
import {
  renderableMatchesQuery,
  tokensFromRenderable,
} from "./search-text-match";
import { hasCjk, MemoryItemSchema, toIsoString, displayTitle } from "./types";
import type { RenderableItem } from "./types";

const RECENT_SCAN_LIMIT = 400;

const COLLECTION_PREFIX =
  process.env.FIRESTORE_COLLECTION_PREFIX?.trim() || "tech_pulse";
const COLLECTION =
  process.env.TECH_PULSE_FIRESTORE_COLLECTION?.trim() ||
  `${COLLECTION_PREFIX}_memory_items`;
const EARNINGS_COLLECTION = `${COLLECTION_PREFIX}_earnings_reports`;

const SEARCH_LIMIT = 10;

export interface SearchNewsHit {
  id: string;
  title: string;
  href: string;
  tickers: string[];
  delivered_at: string | null;
}

export interface SearchEarningsHit {
  ticker: string;
  company: string;
  quarter_label: string;
  href: string;
  published_at: string | null;
}

export interface SearchResults {
  query: string;
  news: SearchNewsHit[];
  earnings: SearchEarningsHit[];
}

function db() {
  return getFirestore(getApp());
}

function prefixEnd(prefix: string): string {
  return `${prefix}\uf8ff`;
}

function renderableToNewsHit(item: RenderableItem): SearchNewsHit {
  return {
    id: item.id,
    title: displayTitle(item),
    href: `/item/${encodeURIComponent(item.id)}`,
    tickers: (item.tickers ?? []).map((t) => t.trim().toUpperCase()).filter(Boolean),
    delivered_at: item.delivered_at_iso,
  };
}

async function searchNewsRecentFallback(
  query: string,
  limit: number,
  excludeIds: Set<string>,
): Promise<SearchNewsHit[]> {
  const items = await listLatestItems({ limit: RECENT_SCAN_LIMIT });
  const queryTokens = tokenizeQuery(query);
  const ranked: { hit: SearchNewsHit; score: number; at: number }[] = [];

  for (const item of items) {
    if (excludeIds.has(item.id)) continue;
    if (!renderableMatchesQuery(item, query)) continue;
    const hit = renderableToNewsHit(item);
    const score = tokenMatchScore(queryTokens, tokensFromRenderable(item));
    ranked.push({
      hit,
      score: score > 0 ? score : 1,
      at: item.delivered_at_iso ? Date.parse(item.delivered_at_iso) : 0,
    });
  }

  ranked.sort((a, b) => b.score - a.score || b.at - a.at);
  return ranked.slice(0, limit).map((row) => row.hit);
}

function toNewsHit(
  id: string,
  raw: Record<string, unknown>,
): SearchNewsHit | null {
  const parsed = MemoryItemSchema.safeParse({ ...raw, id });
  if (!parsed.success) return null;
  const item = parsed.data;
  return {
    id: item.id,
    title: displayTitle({
      zh_title: item.zh_title,
      title: item.title,
      entity: item.entity,
      zh_summary: item.zh_summary,
      hook: item.hook,
    }),
    href: `/item/${encodeURIComponent(item.id)}`,
    tickers: (item.tickers ?? []).map((t) => t.trim().toUpperCase()).filter(Boolean),
    delivered_at: toIsoString(item.delivered_at),
  };
}

async function searchNewsByTicker(
  ticker: string,
  limit: number,
): Promise<SearchNewsHit[]> {
  const snap = await db()
    .collection(COLLECTION)
    .where("tickers", "array-contains", ticker)
    .limit(limit)
    .get();
  const hits: SearchNewsHit[] = [];
  for (const doc of snap.docs) {
    const hit = toNewsHit(doc.id, (doc.data() || {}) as Record<string, unknown>);
    if (hit) hits.push(hit);
  }
  return hits;
}

async function searchNewsByTitlePrefix(
  field: "title" | "zh_title",
  prefix: string,
  limit: number,
): Promise<SearchNewsHit[]> {
  const snap = await db()
    .collection(COLLECTION)
    .orderBy(field)
    .startAt(prefix)
    .endAt(prefixEnd(prefix))
    .limit(limit)
    .get();
  const hits: SearchNewsHit[] = [];
  for (const doc of snap.docs) {
    const hit = toNewsHit(doc.id, (doc.data() || {}) as Record<string, unknown>);
    if (hit) hits.push(hit);
  }
  return hits;
}

async function searchNewsByTokens(
  queryTokens: string[],
  limit: number,
): Promise<SearchNewsHit[]> {
  if (queryTokens.length === 0) return [];
  const snap = await db()
    .collection(COLLECTION)
    .where("search_tokens", "array-contains-any", queryTokens.slice(0, 30))
    .limit(limit * 3)
    .get();

  const ranked: { hit: SearchNewsHit; score: number; at: number }[] = [];
  for (const doc of snap.docs) {
    const raw = (doc.data() || {}) as Record<string, unknown>;
    const hit = toNewsHit(doc.id, raw);
    if (!hit) continue;
    const docTokens = Array.isArray(raw.search_tokens)
      ? (raw.search_tokens as unknown[]).map(String)
      : [];
    ranked.push({
      hit,
      score: tokenMatchScore(queryTokens, docTokens),
      at: hit.delivered_at ? Date.parse(hit.delivered_at) : 0,
    });
  }

  ranked.sort((a, b) => b.score - a.score || b.at - a.at);
  return ranked
    .filter((row) => row.score > 0)
    .slice(0, limit)
    .map((r) => r.hit);
}

function mergeNewsHits(
  batches: SearchNewsHit[][],
  limit: number,
): SearchNewsHit[] {
  const seen = new Set<string>();
  const out: SearchNewsHit[] = [];
  for (const batch of batches) {
    for (const hit of batch) {
      if (seen.has(hit.id)) continue;
      seen.add(hit.id);
      out.push(hit);
      if (out.length >= limit) return out;
    }
  }
  return out;
}

async function searchNews(
  normalized: NormalizedSearchQuery,
  limit = SEARCH_LIMIT,
): Promise<SearchNewsHit[]> {
  const tasks: Promise<SearchNewsHit[]>[] = [];

  // Primary: keyword tokens (matches any word/CJK bigram, not just title start).
  tasks.push(searchNewsByTokens(tokenizeQuery(normalized.q), limit));

  if (normalized.ticker) {
    tasks.push(searchNewsByTicker(normalized.ticker, limit));
  }

  // Fallback: title-prefix for documents not yet backfilled with search_tokens.
  for (const prefix of titlePrefixBounds(normalized.q)) {
    tasks.push(searchNewsByTitlePrefix("title", prefix, limit));
  }

  if (hasCjk(normalized.q)) {
    tasks.push(searchNewsByTitlePrefix("zh_title", normalized.q, limit));
  }

  const batches = await Promise.all(tasks);
  let merged = mergeNewsHits(batches, limit);
  if (merged.length < limit) {
    const extra = await searchNewsRecentFallback(
      normalized.q,
      limit - merged.length,
      new Set(merged.map((hit) => hit.id)),
    );
    merged = mergeNewsHits([merged, extra], limit);
  }
  return merged;
}

async function searchEarningsByTicker(
  ticker: string,
  limit: number,
): Promise<SearchEarningsHit[]> {
  const rows = await listEarningsReports({ limit, ticker, maxTier: 5 });
  return rows.map((row) => ({
    ticker: row.ticker,
    company: row.company,
    quarter_label: row.quarter_label,
    href: `/earnings/${encodeURIComponent(row.ticker)}`,
    published_at: row.published_at_iso,
  }));
}

async function searchEarningsByCompanyPrefix(
  prefix: string,
  limit: number,
): Promise<SearchEarningsHit[]> {
  const snap = await db()
    .collection(EARNINGS_COLLECTION)
    .orderBy("company")
    .startAt(prefix)
    .endAt(prefixEnd(prefix))
    .limit(limit)
    .get();

  const hits: SearchEarningsHit[] = [];
  const seen = new Set<string>();
  for (const doc of snap.docs) {
    const raw = (doc.data() || {}) as Record<string, unknown>;
    const ticker = String(raw.ticker || "").toUpperCase();
    if (!ticker || seen.has(ticker)) continue;
    seen.add(ticker);
    hits.push({
      ticker,
      company: String(raw.company || ticker),
      quarter_label: String(raw.quarter_label || ""),
      href: `/earnings/${encodeURIComponent(ticker)}`,
      published_at:
        typeof raw.published_at === "string"
          ? raw.published_at
          : raw.published_at instanceof Date
            ? raw.published_at.toISOString()
            : null,
    });
    if (hits.length >= limit) break;
  }
  return hits;
}

function mergeEarningsHits(
  batches: SearchEarningsHit[][],
  limit: number,
): SearchEarningsHit[] {
  const seen = new Set<string>();
  const out: SearchEarningsHit[] = [];
  for (const batch of batches) {
    for (const hit of batch) {
      if (seen.has(hit.ticker)) continue;
      seen.add(hit.ticker);
      out.push(hit);
      if (out.length >= limit) return out;
    }
  }
  return out;
}

async function searchEarnings(
  normalized: NormalizedSearchQuery,
  limit = SEARCH_LIMIT,
): Promise<SearchEarningsHit[]> {
  const tasks: Promise<SearchEarningsHit[]>[] = [];

  if (normalized.ticker) {
    tasks.push(searchEarningsByTicker(normalized.ticker, limit));
  }

  for (const prefix of titlePrefixBounds(normalized.q)) {
    tasks.push(searchEarningsByCompanyPrefix(prefix, limit));
  }

  if (hasCjk(normalized.q)) {
    tasks.push(searchEarningsByCompanyPrefix(normalized.q, limit));
  }

  const batches = await Promise.all(tasks);
  return mergeEarningsHits(batches, limit);
}

export async function searchPortal(query: string): Promise<SearchResults> {
  const normalized = normalizeSearchQuery(query);
  const [news, earnings] = await Promise.all([
    searchNews(normalized),
    searchEarnings(normalized),
  ]);
  return {
    query: normalized.q,
    news,
    earnings,
  };
}
