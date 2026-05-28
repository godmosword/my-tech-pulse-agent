import type { Metadata } from "next";
import Link from "next/link";

import { DataTable, type DataColumn } from "@/components/data/DataTable";
import { Delta } from "@/components/data/Delta";
import { DensePageShell } from "@/components/data/DensePageShell";
import { SourceTag } from "@/components/data/SourceTag";
import { StackedExposureBar } from "@/components/data/StackedExposureBar";
import { StatCard } from "@/components/data/StatCard";
import { buildPortfolioPayload } from "@/lib/portfolio-server";

export const dynamic = "force-dynamic";
export const revalidate = 300;

export const metadata: Metadata = {
  title: "持倉",
  description: "持倉感知、主題曝險與配置漂移（config/portfolio.yaml）。",
};

function fmtUsd(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

type PositionRow = Awaited<ReturnType<typeof buildPortfolioPayload>>["positions"][number];

function tierBadge(tier: string) {
  const base = "rounded border px-2 py-0.5 font-sans text-meta uppercase tracking-wide";
  if (tier === "holding") {
    return (
      <span className={`${base} border-accent/40 bg-accent/10 text-accent`}>持倉</span>
    );
  }
  if (tier === "watchlist") {
    return <span className={`${base} border-rule text-ink-soft`}>觀察</span>;
  }
  return <span className={`${base} border-rule text-ink-faint`}>其他</span>;
}

function rebalanceHint(driftPct: number): string {
  if (driftPct > 2) return "超配 — 可考慮減碼或再平衡（僅提示）";
  if (driftPct < -2) return "低配 — 可考慮補倉或再平衡（僅提示）";
  return "接近目標";
}

export default async function PortfolioPage() {
  const data = await buildPortfolioPayload();
  const topTheme = data.theme_exposure[0];

  const positionColumns: DataColumn<PositionRow>[] = [
    {
      key: "ticker",
      header: "代號",
      render: (row) => (
        <Link href={`/earnings/${row.ticker}`} className="font-semibold text-ink hover:text-accent">
          {row.ticker}
        </Link>
      ),
    },
    {
      key: "shares",
      header: "股數",
      numeric: true,
      render: (row) => row.shares.toLocaleString(),
    },
    {
      key: "market_value",
      header: "市值",
      numeric: true,
      render: (row) => fmtUsd(row.market_value),
    },
    {
      key: "weight_pct",
      header: "權重%",
      numeric: true,
      render: (row) => `${row.weight_pct.toFixed(1)}%`,
    },
    {
      key: "unrealized_pct",
      header: "未實現%",
      numeric: true,
      render: (row) =>
        row.unrealized_pct != null ? <Delta value={row.unrealized_pct} /> : "—",
    },
    { key: "theme", header: "主題", render: (row) => row.theme },
    { key: "tier", header: "分層", render: (row) => tierBadge(row.tier) },
  ];

  return (
    <DensePageShell
      kicker="Portfolio"
      title="持倉總覽"
      description="持倉感知、主題曝險與配置漂移。非投資建議。"
      source={data.source}
      asOf={data.as_of || undefined}
      degraded={!data.priced}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          kicker="總市值"
          value={fmtUsd(data.total_market_value)}
          footnote={!data.priced ? "估值為成本基礎 — 未取到即時報價" : undefined}
          degraded={!data.priced}
        />
        {topTheme && (
          <StatCard
            kicker="最大主題集中度"
            value={`${topTheme.weightPct.toFixed(1)}%`}
            footnote={
              topTheme.weightPct > 50
                ? `${topTheme.theme} — 超過 50% 警示`
                : topTheme.theme
            }
          />
        )}
        <StatCard kicker="持倉檔數" value={data.positions.length} unit="檔" />
      </div>

      <section className="section-band mt-8">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
            持倉明細
          </h2>
          <SourceTag source={data.source} asOf={data.as_of || undefined} degraded={!data.priced} />
        </div>
        {data.positions.length === 0 ? (
          <p className="font-sans text-body text-ink-faint">
            尚無持倉。請編輯 config/portfolio.yaml 或執行 scripts/import_ibkr_portfolio.py。
          </p>
        ) : (
          <DataTable
            columns={positionColumns}
            rows={data.positions}
            rowKey={(row) => row.ticker}
          />
        )}
      </section>

      <section className="section-band mt-8">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
            主題曝險
          </h2>
          {topTheme && topTheme.weightPct > 50 && (
            <span className="font-sans text-meta font-semibold text-warn">
              {topTheme.theme} 超過 50%
            </span>
          )}
        </div>
        <StackedExposureBar
          segments={data.theme_exposure.map((row) => ({
            label: row.theme,
            pct: row.weightPct,
            theme: row.theme,
          }))}
        />
      </section>

      <section className="section-band mt-8">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          配置漂移
        </h2>
        <p className="mt-1 font-sans text-meta text-ink-faint">
          正 drift = 超配；負 drift = 低配（相對目標配置）。
        </p>
        <ul className="mt-4 divide-y divide-rule">
          {data.allocation_drift.map((row) => (
            <li
              key={row.theme}
              className="flex flex-col gap-1 py-3 sm:flex-row sm:flex-wrap sm:items-baseline sm:justify-between"
            >
              <span className="font-sans text-body font-semibold text-ink">{row.theme}</span>
              <span className="data-num font-sans text-meta text-ink-soft">
                目前 {row.currentPct.toFixed(1)}% · 目標 {row.targetPct.toFixed(1)}%
              </span>
              <span
                className={`w-full font-sans text-meta ${
                  row.driftPct > 2
                    ? "text-warn"
                    : row.driftPct < -2
                      ? "text-info"
                      : "text-ink-faint"
                }`}
              >
                drift {row.driftPct >= 0 ? "+" : ""}
                {row.driftPct.toFixed(1)}% — {rebalanceHint(row.driftPct)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </DensePageShell>
  );
}
