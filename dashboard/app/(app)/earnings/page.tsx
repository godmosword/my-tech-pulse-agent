import type { Metadata } from "next";
import Link from "next/link";

import { BackLink } from "@/components/BackLink";
import { Breadcrumb } from "@/components/Breadcrumb";
import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
import { listEarningsReports } from "@/lib/earnings-firestore";
import { formatDashboardDateTime } from "@/lib/format-datetime";

export const dynamic = "force-dynamic";
export const revalidate = 300;

export const metadata: Metadata = {
  title: "財報",
  description: "美股 AI 半導體財報雷達：以 SEC 申報時間排序的結構化季報指標。",
};

function metricBadge(
  metrics: { metric: string; label_zh: string; value: number; unit?: string }[],
  name: string
) {
  const m = metrics.find((x) => x.metric === name);
  if (!m) return null;
  const value = Number(m.value);
  if (!Number.isFinite(value)) return null;
  const unit = m.unit === "USD/share" ? "" : m.unit === "USD" ? " USD" : "";
  const display =
    m.metric.startsWith("eps")
      ? value.toFixed(2)
      : value >= 1e9
        ? `${(value / 1e9).toFixed(2)}B`
        : value.toLocaleString();
  return (
    <span className="rounded border border-rule px-2 py-0.5 font-mono text-meta text-ink-soft">
      {m.label_zh} {display}
      {unit}
    </span>
  );
}

export default async function EarningsPage() {
  const rows = await listEarningsReports({ limit: 40, maxTier: 5 });

  return (
    <div>
      <BackLink href="/invest" label="返回投資中樞" />
      <Breadcrumb
        items={[
          { label: "投資", href: "/invest" },
          { label: "財報" },
        ]}
      />
      <Kicker tone="accent">Earnings Radar</Kicker>
      <h1 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-ink">
        財報雷達
      </h1>
      <p className="mt-3 max-w-prose font-sans text-body text-ink-soft">
        以 SEC 申報時間（published_at）排序；季度標籤依各公司 fiscal
        calendar，不以日曆季推斷。
      </p>
      <Hairline className="mt-6" />

      {rows.length === 0 ? (
        <p className="mt-10 font-sans text-body text-ink-faint">
          尚無財報資料。Pipeline 執行後會寫入{" "}
          <code className="font-mono text-meta">tech_pulse_earnings_reports</code>。
        </p>
      ) : (
        <ul className="mt-8 divide-y divide-rule">
          {rows.map((row) => (
            <li key={row.report_id} className="py-6">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <Link
                  href={`/earnings/${encodeURIComponent(row.ticker)}`}
                  className="font-serif text-xl font-semibold text-ink hover:text-accent"
                >
                  {row.ticker}
                </Link>
                {row.tier != null && (
                  <span className="font-sans text-meta uppercase tracking-widest text-ink-faint">
                    Tier {row.tier}
                  </span>
                )}
                <span className="font-sans text-meta text-ink-faint">
                  {formatDashboardDateTime(row.published_at_iso) || "—"}
                </span>
              </div>
              <p className="mt-1 font-sans text-body text-ink-soft">
                <Link
                  href={`/earnings/report/${encodeURIComponent(row.report_id)}`}
                  className="hover:text-accent hover:underline"
                >
                  {row.quarter_label}
                </Link>
                {row.scorecard?.headline_verdict && (
                  <span className="ml-2 text-meta text-ink-faint">
                    · {row.scorecard.headline_verdict}
                  </span>
                )}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {metricBadge(row.headline_metrics, "revenue")}
                {metricBadge(row.headline_metrics, "eps_diluted")}
                {metricBadge(row.headline_metrics, "eps_basic")}
                <span className="font-sans text-meta text-ink-faint">
                  {row.confidence}
                </span>
              </div>
              {row.investment_takeaway_zh && (
                <p className="mt-3 font-sans text-body text-ink">
                  {row.investment_takeaway_zh}
                </p>
              )}
              {row.source_url && (
                <a
                  href={row.source_url}
                  className="mt-2 inline-block font-sans text-meta text-accent hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  SEC filing
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
