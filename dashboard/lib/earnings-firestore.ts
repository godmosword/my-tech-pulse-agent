import "server-only";
import {
  FieldPath,
  getFirestore,
  type QueryDocumentSnapshot,
} from "firebase-admin/firestore";

import { getApp } from "./firestore";

const COLLECTION_PREFIX =
  process.env.FIRESTORE_COLLECTION_PREFIX?.trim() || "tech_pulse";
const EARNINGS_COLLECTION = `${COLLECTION_PREFIX}_earnings_reports`;

interface MetricValueRow {
  actual?: number | null;
  estimate?: number | null;
  surprise_pct?: number | null;
  yoy_pct?: number | null;
  accounting_basis?: string;
  actual_source?: string;
  estimate_source?: string;
}

interface ScorecardRow {
  revenue?: MetricValueRow | null;
  eps?: MetricValueRow | null;
  gross_margin_pct?: MetricValueRow | null;
  headline_verdict?: string;
}

interface PriceReactionRow {
  earnings_date?: string | null;
  session?: string;
  ret_1d_pct?: number | null;
  ret_5d_pct?: number | null;
  excess_1d_pct?: number | null;
  excess_5d_pct?: number | null;
  bench_symbol?: string;
  reaction_label?: string;
  degraded?: boolean;
}

interface ValuationRatiosRow {
  gross_margin?: number | null;
  operating_margin?: number | null;
  net_margin?: number | null;
  roe?: number | null;
  roic?: number | null;
  debt_to_equity?: number | null;
  fcf_margin?: number | null;
  source?: string;
  period_matched?: string;
}

interface SurprisePointRow {
  period: string;
  eps_actual?: number | null;
  eps_estimate?: number | null;
  surprise_pct?: number | null;
}

interface FinancialHealthRow {
  fcf?: number | null;
  fcf_conversion_pct?: number | null;
  roic_trend?: string;
  shareholder_returns_zh?: string;
  source_conflicts?: string[];
}

export interface SignalFactorRow {
  name: string;
  score?: number | null;
  weight: number;
  detail_zh: string;
  available: boolean;
}

export interface InvestmentSignalRow {
  score?: number | null;
  rating: string;
  conviction: string;
  factors?: SignalFactorRow[];
  rationale_zh?: string;
  as_of?: string | null;
}

export interface EarningsReportRow {
  report_id: string;
  ticker: string;
  company: string;
  tier: number | null;
  fiscal_year: number | null;
  fiscal_period: string;
  quarter_label: string;
  published_at_iso: string | null;
  confidence: string;
  schema_version: string;
  headline_metrics: Array<{
    metric: string;
    label_zh: string;
    value: number;
    unit?: string;
    source_tag?: string;
  }>;
  scorecard?: ScorecardRow | null;
  rendered_markdown_zh?: string;
  transcript_status?: string;
  investment_takeaway_zh?: string;
  ai_infra_signal?: string;
  risk_flags?: string[];
  source_url: string;
  price_reaction?: PriceReactionRow | null;
  ratios?: ValuationRatiosRow | null;
  surprise_history?: SurprisePointRow[];
  financial_health?: FinancialHealthRow | null;
  investment_signal?: InvestmentSignalRow | null;
}

function metricFromHeadline(
  metrics: EarningsReportRow["headline_metrics"],
  name: string
): number | undefined {
  const m = metrics.find((x) => x.metric === name);
  return m?.value;
}

/** v2 documents → minimal v3 scorecard view (no surprise, basis Unknown). */
function scorecardFromLegacyHeadline(
  headline_metrics: EarningsReportRow["headline_metrics"]
): ScorecardRow {
  const revenue = metricFromHeadline(headline_metrics, "revenue");
  const eps =
    metricFromHeadline(headline_metrics, "eps_diluted") ??
    metricFromHeadline(headline_metrics, "eps_basic");
  const gross = metricFromHeadline(headline_metrics, "gross_profit");
  const rev = metricFromHeadline(headline_metrics, "revenue");
  const gmPct =
    revenue != null && rev != null && rev !== 0 && gross != null
      ? (gross / rev) * 100
      : undefined;

  return {
    revenue: revenue != null ? { actual: revenue, accounting_basis: "Unknown" } : null,
    eps: eps != null ? { actual: eps, accounting_basis: "Unknown" } : null,
    gross_margin_pct:
      gmPct != null ? { actual: gmPct, accounting_basis: "Unknown" } : null,
    headline_verdict: "無法判定",
  };
}

function parseScorecard(raw: Record<string, unknown>): ScorecardRow | null {
  const sc = raw.scorecard;
  if (!sc || typeof sc !== "object") return null;
  return sc as ScorecardRow;
}

function toIso(value: unknown): string | null {
  if (!value) return null;
  if (typeof value === "string") return value;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "object" && value !== null && "toDate" in value) {
    try {
      return (value as { toDate: () => Date }).toDate().toISOString();
    } catch {
      return null;
    }
  }
  return null;
}

function toRow(id: string, raw: Record<string, unknown>): EarningsReportRow | null {
  const ticker = String(raw.ticker || "");
  if (!ticker) return null;
  const docs = Array.isArray(raw.source_documents) ? raw.source_documents : [];
  const firstDoc = (docs[0] || {}) as Record<string, unknown>;
  const schemaVersion = String(raw.schema_version || "earnings_v2");
  const headline_metrics = Array.isArray(raw.headline_metrics)
    ? (raw.headline_metrics as EarningsReportRow["headline_metrics"])
    : [];
  let scorecard = parseScorecard(raw);
  if (!scorecard && schemaVersion !== "earnings_v3" && headline_metrics.length > 0) {
    scorecard = scorecardFromLegacyHeadline(headline_metrics);
  }

  return {
    report_id: String(raw.report_id || id),
    ticker,
    company: String(raw.company || ticker),
    tier: typeof raw.tier === "number" ? raw.tier : null,
    fiscal_year: typeof raw.fiscal_year === "number" ? raw.fiscal_year : null,
    fiscal_period: String(raw.fiscal_period || ""),
    quarter_label: String(raw.quarter_label || ""),
    published_at_iso: toIso(raw.published_at),
    confidence: String(raw.confidence || "medium"),
    schema_version: schemaVersion,
    headline_metrics,
    scorecard,
    rendered_markdown_zh: raw.rendered_markdown_zh
      ? String(raw.rendered_markdown_zh)
      : undefined,
    transcript_status: raw.transcript_status
      ? String(raw.transcript_status)
      : undefined,
    investment_takeaway_zh: raw.investment_takeaway_zh
      ? String(raw.investment_takeaway_zh)
      : undefined,
    ai_infra_signal: raw.ai_infra_signal ? String(raw.ai_infra_signal) : undefined,
    risk_flags: Array.isArray(raw.risk_flags)
      ? raw.risk_flags.map(String)
      : undefined,
    source_url: String(firstDoc.filing_url || ""),
    price_reaction: raw.price_reaction
      ? (raw.price_reaction as PriceReactionRow)
      : undefined,
    ratios: raw.ratios ? (raw.ratios as ValuationRatiosRow) : undefined,
    surprise_history: Array.isArray(raw.surprise_history)
      ? (raw.surprise_history as SurprisePointRow[])
      : undefined,
    financial_health: raw.financial_health
      ? (raw.financial_health as FinancialHealthRow)
      : undefined,
    investment_signal: raw.investment_signal
      ? (raw.investment_signal as InvestmentSignalRow)
      : undefined,
  };
}

function db() {
  return getFirestore(getApp());
}

function publishedAtMs(iso: string | null): number {
  if (!iso) return 0;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : 0;
}

function sortByPublishedDesc(rows: EarningsReportRow[]): EarningsReportRow[] {
  return [...rows].sort(
    (a, b) => publishedAtMs(b.published_at_iso) - publishedAtMs(a.published_at_iso),
  );
}

export interface EarningsFirestoreCursor {
  publishedAtIso: string;
  reportId: string;
}

function publishedAtFromIso(iso: string): Date {
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) {
    throw new Error(`invalid published_at cursor: ${iso}`);
  }
  return new Date(ms);
}

function passesTier(row: EarningsReportRow, maxTier: number): boolean {
  return row.tier == null || row.tier <= maxTier;
}

function collectTierFiltered(
  docs: QueryDocumentSnapshot[],
  maxTier: number,
): EarningsReportRow[] {
  const rows: EarningsReportRow[] = [];
  for (const doc of docs) {
    const row = toRow(doc.id, (doc.data() || {}) as Record<string, unknown>);
    if (!row) continue;
    if (!passesTier(row, maxTier)) continue;
    rows.push(row);
  }
  return rows;
}

export async function listEarningsReports({
  limit = 30,
  ticker,
  maxTier = 5,
}: {
  limit?: number;
  ticker?: string;
  maxTier?: number;
} = {}): Promise<EarningsReportRow[]> {
  // Ticker filter + orderBy requires a composite Firestore index and fails at
  // runtime on Vercel. Filter by ticker only, then sort in memory.
  const snap = ticker
    ? await db()
        .collection(EARNINGS_COLLECTION)
        .where("ticker", "==", ticker.toUpperCase())
        .limit(limit * 3)
        .get()
    : await db()
        .collection(EARNINGS_COLLECTION)
        .orderBy("published_at", "desc")
        .limit(limit * 3)
        .get();

  const rows = collectTierFiltered(snap.docs, maxTier);
  return sortByPublishedDesc(rows).slice(0, limit);
}

export async function listEarningsReportsPage({
  limit = 30,
  ticker,
  maxTier = 5,
  cursor,
}: {
  limit?: number;
  ticker?: string;
  maxTier?: number;
  cursor?: EarningsFirestoreCursor;
}): Promise<{
  items: EarningsReportRow[];
  hasMore: boolean;
  lastCursor: EarningsFirestoreCursor | null;
}> {
  const batchSize = Math.max(limit * 3, 30);
  const collected: EarningsReportRow[] = [];
  let scanCursor = cursor;
  let hasMoreInFirestore = true;

  while (collected.length < limit + 1 && hasMoreInFirestore) {
    let snap;
    if (ticker) {
      snap = await db()
        .collection(EARNINGS_COLLECTION)
        .where("ticker", "==", ticker.toUpperCase())
        .limit(batchSize + 1)
        .get();
      hasMoreInFirestore = false;
    } else {
      let query = db()
        .collection(EARNINGS_COLLECTION)
        .orderBy("published_at", "desc")
        .orderBy(FieldPath.documentId(), "desc");
      if (scanCursor) {
        query = query.startAfter(
          publishedAtFromIso(scanCursor.publishedAtIso),
          scanCursor.reportId,
        );
      }
      snap = await query.limit(batchSize + 1).get();
      hasMoreInFirestore = snap.docs.length > batchSize;
    }

    const docs = snap.docs.slice(0, batchSize);
    const rows = sortByPublishedDesc(collectTierFiltered(docs, maxTier));
    for (const row of rows) {
      if (
        scanCursor &&
        publishedAtMs(row.published_at_iso) === publishedAtMs(scanCursor.publishedAtIso) &&
        row.report_id === scanCursor.reportId
      ) {
        continue;
      }
      collected.push(row);
      if (collected.length >= limit + 1) break;
    }

    const lastDoc = docs.at(-1);
    if (!ticker && lastDoc) {
      const lastRow = toRow(
        lastDoc.id,
        (lastDoc.data() || {}) as Record<string, unknown>,
      );
      if (lastRow?.published_at_iso) {
        scanCursor = {
          publishedAtIso: lastRow.published_at_iso,
          reportId: lastRow.report_id,
        };
      }
    }

    if (!hasMoreInFirestore || ticker) break;
  }

  const items = collected.slice(0, limit);
  const last = items.at(-1);
  const hasMore = collected.length > limit || (items.length === limit && hasMoreInFirestore);

  return {
    items,
    hasMore,
    lastCursor: last?.published_at_iso
      ? { publishedAtIso: last.published_at_iso, reportId: last.report_id }
      : null,
  };
}

export async function getEarningsReport(
  reportId: string
): Promise<EarningsReportRow | null> {
  const doc = await db().collection(EARNINGS_COLLECTION).doc(reportId).get();
  if (!doc.exists) return null;
  return toRow(doc.id, (doc.data() || {}) as Record<string, unknown>);
}

/** Upcoming watchlist earnings (vendor calendar stub returns empty until keys wired). */
/** Reports with published_at on or after `since` (UTC), Taipei-oriented callers pass start of day UTC+8). */
export async function listEarningsSince(
  since: Date,
  { limit = 12, maxTier = 5 }: { limit?: number; maxTier?: number } = {},
): Promise<EarningsReportRow[]> {
  const rows = await listEarningsReports({ limit: limit * 4, maxTier });
  const sinceMs = since.getTime();
  return rows
    .filter((r) => publishedAtMs(r.published_at_iso) >= sinceMs)
    .slice(0, limit);
}

const EARNINGS_SINCE_SCAN_CAP = 500;

export async function listEarningsSinceAll(
  since: Date,
  { maxTier = 5 }: { maxTier?: number } = {},
): Promise<EarningsReportRow[]> {
  const sinceMs = since.getTime();
  const collected: EarningsReportRow[] = [];
  let cursor: EarningsFirestoreCursor | undefined;
  let hasMore = true;

  while (hasMore && collected.length < EARNINGS_SINCE_SCAN_CAP) {
    const page = await listEarningsReportsPage({
      limit: 80,
      maxTier,
      cursor,
    });
    for (const row of page.items) {
      if (publishedAtMs(row.published_at_iso) < sinceMs) {
        hasMore = false;
        break;
      }
      collected.push(row);
    }
    if (!page.hasMore || !page.lastCursor) break;
    cursor = page.lastCursor;
  }

  return collected;
}

export async function listEarningsPeers(
  tier: number,
  excludeTicker?: string,
  limit = 8,
): Promise<EarningsReportRow[]> {
  const rows = await listEarningsReports({ limit: 60, maxTier: 5 });
  return rows
    .filter((r) => r.tier === tier && r.ticker !== excludeTicker?.toUpperCase())
    .slice(0, limit);
}
