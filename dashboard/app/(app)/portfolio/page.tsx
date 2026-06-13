import type { Metadata } from "next";
import Link from "next/link";

import { DataTable, type DataColumn } from "@/components/data/DataTable";
import { Delta } from "@/components/data/Delta";
import { DensePageShell } from "@/components/data/DensePageShell";
import { SourceTag } from "@/components/data/SourceTag";
import { StackedExposureBar } from "@/components/data/StackedExposureBar";
import { StatCard } from "@/components/data/StatCard";
import { fmtUsd } from "@/lib/format-numbers";
import { ExposurePassthroughCard } from "@/components/ExposurePassthroughCard";
import { THEME_LABELS } from "@/lib/macro-data";
import { exposurePassthrough } from "@/lib/exposure-passthrough";
import { buildPortfolioPayload } from "@/lib/portfolio-server";
import { PortfolioEditorPrototype } from "@/components/PortfolioEditorPrototype";
import { loadPortfolio } from "@/lib/portfolio-data";
import {
  loadClustersSnapshot,
  loadCompanyRelationships,
} from "@/lib/relationship-data";
import { watchlistTickerSet } from "@/lib/pillar-map";

export const dynamic = "force-dynamic";
export const revalidate = 300;

export const metadata: Metadata = {
  title: "持倉",
  description: "持倉感知、主題曝險與配置漂移（config/portfolio.yaml）。",
};

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

function themeLabel(theme: string): string {
  return THEME_LABELS[theme] ?? theme;
}

function driftStatus(driftPct: number): string {
  if (driftPct > 2) return "超配";
  if (driftPct < -2) return "低配";
  return "接近目標";
}

type DriftRow = Awaited<ReturnType<typeof buildPortfolioPayload>>["allocation_drift"][number];

export default async function PortfolioPage() {
  const data = await buildPortfolioPayload();
  const yamlSource = loadPortfolio();
  const topTheme = data.theme_exposure[0];

  const heldTickers = data.positions
    .filter((p) => p.tier === "holding")
    .map((p) => p.ticker);
  const relMap: Record<string, ReturnType<typeof loadCompanyRelationships>> = {};
  for (const t of heldTickers) {
    relMap[t] = loadCompanyRelationships(t);
  }
  const clustersSnap = loadClustersSnapshot();
  const indirectExposures = exposurePassthrough(
    heldTickers.map((ticker) => ({ ticker })),
    relMap,
    clustersSnap?.clusters ?? null,
    watchlistTickerSet(),
  );

  const driftColumns: DataColumn<DriftRow>[] = [
    {
      key: "theme",
      header: "主題",
      render: (row) => themeLabel(row.theme),
    },
    {
      key: "currentPct",
      header: "目前%",
      numeric: true,
      render: (row) => `${row.currentPct.toFixed(1)}%`,
    },
    {
      key: "targetPct",
      header: "目標%",
      numeric: true,
      render: (row) => `${row.targetPct.toFixed(1)}%`,
    },
    {
      key: "driftPct",
      header: "偏差",
      numeric: true,
      render: (row) => <Delta value={row.driftPct} suffix="%" />,
    },
    {
      key: "status",
      header: "狀態",
      render: (row) => {
        const status = driftStatus(row.driftPct);
        const tone =
          row.driftPct > 2
            ? "text-warn"
            : row.driftPct < -2
              ? "text-info"
              : "text-ink-faint";
        return <span className={`font-sans text-meta ${tone}`}>{status}</span>;
      },
    },
  ];

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
    { key: "theme", header: "主題", render: (row) => themeLabel(row.theme) },
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
      backHref="/invest"
      backLabel="返回投資中樞"
      breadcrumb={[
        { label: "投資", href: "/invest" },
        { label: "持倉" },
      ]}
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
                ? `${themeLabel(topTheme.theme)} — 超過 50% 警示`
                : themeLabel(topTheme.theme)
            }
          />
        )}
        <StatCard kicker="持倉檔數" value={data.positions.length} unit="檔" />
      </div>

      <ExposurePassthroughCard exposures={indirectExposures} />

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
              {themeLabel(topTheme.theme)} 超過 50%
            </span>
          )}
        </div>
        <StackedExposureBar
          segments={data.theme_exposure.map((row) => ({
            label: themeLabel(row.theme),
            pct: row.weightPct,
            theme: row.theme,
          }))}
        />
      </section>

      <section className="section-band mt-8">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          目標配置偏差
        </h2>
        <p className="mt-1 font-sans text-meta text-ink-faint">
          比較「持倉主題占比」與 config/portfolio.yaml 的 target_allocation。偏差 = 目前% −
          目標%；正數代表超配、負數代表低配（僅供再平衡參考，非投資建議）。
        </p>
        <div className="mt-4">
          <DataTable
            columns={driftColumns}
            rows={data.allocation_drift}
            rowKey={(row) => row.theme}
          />
        </div>
      </section>

      <PortfolioEditorPrototype
        initialPositions={yamlSource.positions.map((p) => ({
          ticker: p.ticker,
          shares: p.shares,
          avg_cost: p.avgCost,
        }))}
        asOf={yamlSource.asOf}
        baseCurrency={yamlSource.baseCurrency}
      />
    </DensePageShell>
  );
}
