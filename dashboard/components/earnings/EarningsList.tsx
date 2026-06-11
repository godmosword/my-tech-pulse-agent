"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { LoadMoreButton } from "@/components/LoadMoreButton";
import type { EarningsReportRow } from "@/lib/earnings-firestore";

type Props = {
  initialItems: EarningsReportRow[];
  initialNextCursor: string | null;
  pageSize: number;
};

function formatTp(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function metricBadge(
  metrics: { metric: string; label_zh: string; value: number; unit?: string }[],
  name: string,
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

export function EarningsList({ initialItems, initialNextCursor, pageSize }: Props) {
  const [items, setItems] = useState(initialItems);
  const [nextCursor, setNextCursor] = useState(initialNextCursor);

  const onLoadMore = useCallback(async () => {
    if (!nextCursor) return;
    const params = new URLSearchParams({
      limit: String(pageSize),
      max_tier: "5",
      cursor: nextCursor,
    });
    const res = await fetch(`/api/v1/earnings?${params.toString()}`);
    if (!res.ok) throw new Error("fetch failed");
    const body = (await res.json()) as {
      items: EarningsReportRow[];
      nextCursor: string | null;
    };
    setItems((prev) => [...prev, ...body.items]);
    setNextCursor(body.nextCursor);
  }, [nextCursor, pageSize]);

  if (items.length === 0) {
    return (
      <p className="mt-10 font-sans text-body text-ink-faint">
        尚無財報資料。Pipeline 執行後會寫入{" "}
        <code className="font-mono text-meta">tech_pulse_earnings_reports</code>。
      </p>
    );
  }

  return (
    <>
      <ul className="mt-8 divide-y divide-rule">
        {items.map((row) => (
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
                {formatTp(row.published_at_iso)}
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
      <LoadMoreButton hasMore={Boolean(nextCursor)} onLoadMore={onLoadMore} />
    </>
  );
}
