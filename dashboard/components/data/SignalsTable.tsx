"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, type DataColumn } from "@/components/data/DataTable";
import { RatingBadge } from "@/components/data/RatingBadge";
import type { PortfolioTier } from "@/lib/portfolio-metrics";
import { PortfolioTierBadge } from "@/components/data/PortfolioTierBadge";

const FACTOR_LABELS: Record<string, string> = {
  fundamental_momentum: "動能",
  surprise: "驚喜",
  market_confirmation: "市場",
  quality: "品質",
};

type SignalListItem = {
  report_id: string;
  ticker: string;
  quarter_label: string;
  score: number;
  rating: string;
  conviction: string;
  top_factor: string;
  portfolio_tier: PortfolioTier;
  factors?: Array<{ name: string; score: number | null; available: boolean }>;
};

type Props = {
  items: SignalListItem[];
};

function tierBadge(pt: PortfolioTier) {
  return <PortfolioTierBadge tier={pt} />;
}

function FactorMiniBars({
  factors,
}: {
  factors: Array<{ name: string; score: number | null; available: boolean }>;
}) {
  return (
    <div className="mt-3 grid gap-2 border-t border-rule pt-3">
      {factors.map((f) => {
        const score = f.available && f.score != null ? f.score : null;
        const barColor =
          score == null
            ? "bg-ink-faint/25"
            : score >= 60
              ? "bg-pos/70"
              : score <= 40
                ? "bg-neg/70"
                : "bg-warn/60";
        return (
          <div key={f.name}>
            <div className="mb-1 flex justify-between font-sans text-meta text-ink-soft">
              <span>{FACTOR_LABELS[f.name] ?? f.name}</span>
              <span className="data-num">{score != null ? score.toFixed(0) : "—"}</span>
            </div>
            <div className="h-1.5 rounded-full bg-ink-faint/15">
              <div
                className={`h-1.5 rounded-full ${barColor}`}
                style={{ width: score != null ? `${Math.min(100, score)}%` : "0%" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function SignalsTable({ items }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const desktopColumns: DataColumn<SignalListItem>[] = [
    {
      key: "ticker",
      header: "代號",
      align: "left",
      render: (row) => (
        <span className="inline-flex flex-wrap items-center gap-1">
          <Link href={`/earnings/${row.ticker}`} className="font-semibold text-ink hover:text-accent">
            {row.ticker}
          </Link>
          {tierBadge(row.portfolio_tier)}
        </span>
      ),
    },
    {
      key: "quarter_label",
      header: "季度",
      render: (row) => (
        <Link
          href={`/earnings/report/${encodeURIComponent(row.report_id)}`}
          className="text-ink-soft hover:text-accent"
        >
          {row.quarter_label}
        </Link>
      ),
    },
    {
      key: "score",
      header: "分數",
      numeric: true,
      render: (row) => row.score.toFixed(1),
    },
    {
      key: "rating",
      header: "評級",
      render: (row) => <RatingBadge rating={row.rating} conviction={row.conviction} />,
    },
    {
      key: "conviction",
      header: "信心",
      render: (row) => row.conviction,
    },
    {
      key: "top_factor",
      header: "主因子",
      render: (row) => FACTOR_LABELS[row.top_factor] ?? row.top_factor,
    },
  ];

  // Mobile: compact list — ticker + score + badge; tap for factors
  return (
    <>
      <div className="space-y-2 sm:hidden">
        {items.map((row, idx) => {
          const open = expandedId === row.report_id;
          return (
            <div
              key={row.report_id}
              className={`section-band ${row.portfolio_tier === "holding" ? "ring-1 ring-accent/20" : ""}`}
            >
              <div className="flex w-full items-center justify-between gap-3">
                <div className="min-w-0">
                  <Link
                    href={`/earnings/${row.ticker}`}
                    className="font-semibold text-ink hover:text-accent"
                  >
                    {row.ticker}
                  </Link>
                  <span className="ml-2 font-sans text-meta text-ink-faint">#{idx + 1}</span>
                </div>
                <button
                  type="button"
                  className="flex min-h-[44px] shrink-0 items-center gap-2 rounded-sm px-1 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  onClick={() => setExpandedId(open ? null : row.report_id)}
                  aria-expanded={open}
                  aria-controls={`signal-factors-${row.report_id}`}
                  aria-label={`${open ? "收合" : "展開"} ${row.ticker} 因子細項`}
                >
                  <span className="stat-hero text-2xl text-ink">{row.score.toFixed(0)}</span>
                  <RatingBadge rating={row.rating} conviction={row.conviction} />
                </button>
              </div>
              {open && row.factors && row.factors.length > 0 && (
                <div id={`signal-factors-${row.report_id}`}>
                  <FactorMiniBars factors={row.factors} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="hidden sm:block">
        <DataTable
          columns={[
            {
              key: "rank",
              header: "#",
              numeric: true,
              mobileLabel: "#",
              render: (row) => {
                const idx = items.indexOf(row);
                return String(idx + 1);
              },
            },
            ...desktopColumns,
          ]}
          rows={items}
          rowKey={(row) => row.report_id}
          rowClassName={(row) => (row.portfolio_tier === "holding" ? "bg-accent/5" : undefined)}
        />
      </div>
    </>
  );
}
