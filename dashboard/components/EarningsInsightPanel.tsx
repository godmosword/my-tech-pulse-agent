import Link from "next/link";

import type { EarningsReportRow } from "@/lib/earnings-firestore";
import { Kicker } from "./Kicker";

interface EarningsInsightPanelProps {
  symbol: string;
  enabled: boolean;
  reason?: string;
  hint?: string;
  report?: EarningsReportRow;
  reportUrlPath?: string;
}

function excerptMarkdown(md: string, maxLen = 320): string {
  const plain = md
    .replace(/^#+\s+/gm, "")
    .replace(/\*\*/g, "")
    .replace(/\n+/g, " ")
    .trim();
  if (plain.length <= maxLen) return plain;
  return `${plain.slice(0, maxLen).trim()}…`;
}

export function EarningsInsightPanel({
  symbol,
  enabled,
  reason,
  hint,
  report,
  reportUrlPath,
}: EarningsInsightPanelProps) {
  if (!enabled || !report) {
    return (
      <section className="mt-6 rounded border border-rule bg-paper-tint px-4 py-4">
        <Kicker>Insight</Kicker>
        <p className="mt-2 font-sans text-body text-ink-soft">
          {symbol} 尚無可用 insight
          {reason === "no_earnings_report" ? "（尚無歸檔報告）" : ""}。
        </p>
        {hint && (
          <p className="mt-1 font-sans text-meta text-ink-faint">{hint}</p>
        )}
        <Link
          href="/invest"
          className="mt-2 inline-block font-sans text-meta text-accent underline-offset-4 hover:underline"
        >
          返回投資中樞
        </Link>
      </section>
    );
  }

  const md = report.rendered_markdown_zh?.trim() ?? "";
  const takeaway = report.investment_takeaway_zh?.trim() ?? "";

  return (
    <section className="mt-6 space-y-3 rounded border border-rule bg-paper-tint px-4 py-4">
      <Kicker>最新 Insight · {report.quarter_label}</Kicker>
      {report.investment_signal && (
        <p className="font-sans text-meta text-ink">
          訊號：
          <span className="font-semibold">{report.investment_signal.rating}</span>
          {report.investment_signal.score != null
            ? ` · ${report.investment_signal.score.toFixed(0)}`
            : ""}
          {report.scorecard?.headline_verdict
            ? ` · ${report.scorecard.headline_verdict}`
            : ""}
        </p>
      )}
      {takeaway && (
        <p className="font-sans text-editorial-body text-ink">{takeaway}</p>
      )}
      {md && (
        <p className="font-sans text-body text-ink-soft">{excerptMarkdown(md)}</p>
      )}
      {reportUrlPath && (
        <Link
          href={reportUrlPath}
          className="inline-block font-sans text-meta text-accent underline-offset-4 hover:underline"
        >
          閱讀完整深度報告 →
        </Link>
      )}
    </section>
  );
}
