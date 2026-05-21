import "server-only";
import { getFirestore } from "firebase-admin/firestore";

import { getApp } from "./firestore";

const COLLECTION_PREFIX =
  process.env.FIRESTORE_COLLECTION_PREFIX?.trim() || "tech_pulse";
const EARNINGS_COLLECTION = `${COLLECTION_PREFIX}_earnings_reports`;

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
  headline_metrics: Array<{
    metric: string;
    label_zh: string;
    value: number;
    unit?: string;
    source_tag?: string;
  }>;
  investment_takeaway_zh?: string;
  ai_infra_signal?: string;
  risk_flags?: string[];
  source_url: string;
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
    headline_metrics: Array.isArray(raw.headline_metrics)
      ? (raw.headline_metrics as EarningsReportRow["headline_metrics"])
      : [],
    investment_takeaway_zh: raw.investment_takeaway_zh
      ? String(raw.investment_takeaway_zh)
      : undefined,
    ai_infra_signal: raw.ai_infra_signal ? String(raw.ai_infra_signal) : undefined,
    risk_flags: Array.isArray(raw.risk_flags)
      ? raw.risk_flags.map(String)
      : undefined,
    source_url: String(firstDoc.filing_url || ""),
  };
}

function db() {
  return getFirestore(getApp());
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
  let query = db()
    .collection(EARNINGS_COLLECTION)
    .orderBy("published_at", "desc")
    .limit(limit * 3);

  if (ticker) {
    query = db()
      .collection(EARNINGS_COLLECTION)
      .where("ticker", "==", ticker.toUpperCase())
      .orderBy("published_at", "desc")
      .limit(limit);
  }

  const snap = await query.get();
  const rows: EarningsReportRow[] = [];
  for (const doc of snap.docs) {
    const row = toRow(doc.id, (doc.data() || {}) as Record<string, unknown>);
    if (!row) continue;
    if (row.tier != null && row.tier > maxTier) continue;
    rows.push(row);
    if (rows.length >= limit) break;
  }
  return rows;
}

export async function getEarningsReport(
  reportId: string
): Promise<EarningsReportRow | null> {
  const doc = await db().collection(EARNINGS_COLLECTION).doc(reportId).get();
  if (!doc.exists) return null;
  return toRow(doc.id, (doc.data() || {}) as Record<string, unknown>);
}

/** Upcoming watchlist earnings (vendor calendar stub returns empty until keys wired). */
export async function listEarningsCalendar(
  horizonDays = 30
): Promise<
  Array<{
    ticker: string;
    company: string;
    tier: number | null;
    event_date_iso: string | null;
    note: string;
  }>
> {
  void horizonDays;
  const rows = await listEarningsReports({ limit: 50, maxTier: 5 });
  return rows.map((r) => ({
    ticker: r.ticker,
    company: r.company,
    tier: r.tier,
    event_date_iso: r.published_at_iso,
    note: "recent_filing",
  }));
}
