import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { DensePageShell } from "@/components/data/DensePageShell";
import { DataTable, type DataColumn } from "@/components/data/DataTable";
import { RatingBadge } from "@/components/data/RatingBadge";
import { SourceTag } from "@/components/data/SourceTag";
import { StackedExposureBar } from "@/components/data/StackedExposureBar";
import { StatCard } from "@/components/data/StatCard";
import { loadBacktestSummary } from "@/lib/backtest-data";
import { listEarningsSince } from "@/lib/earnings-firestore";
import { loadUpcomingEarnings } from "@/lib/earnings-portal";
import { THEME_LABELS, loadMacroContextSnapshot } from "@/lib/macro-data";
import {
  portfolioEnvironment,
  weightedEnvironmentBias,
} from "@/lib/portfolio-metrics";
import { buildPortfolioPayload } from "@/lib/portfolio-server";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "投資",
  description: "持倉、訊號、財報、宏觀與校驗的一頁綜覽。",
};

function fmtUsd(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function themeLabel(theme: string): string {
  return THEME_LABELS[theme] ?? theme;
}

function SectionBand({
  title,
  moreHref,
  moreLabel,
  children,
}: {
  title: string;
  moreHref: string;
  moreLabel: string;
  children: ReactNode;
}) {
  return (
    <section className="section-band mt-8">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          {title}
        </h2>
        <Link
          href={moreHref}
          className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-accent hover:underline"
        >
          {moreLabel}
        </Link>
      </div>
      {children}
    </section>
  );
}

function Pending({ note = "資料準備中" }: { note?: string }) {
  return <p className="font-sans text-body text-ink-faint">{note}</p>;
}

async function PortfolioSection() {
  try {
    const data = await buildPortfolioPayload();
    return (
      <>
        <div className="grid gap-4 sm:grid-cols-2">
          <StatCard
            kicker="總市值"
            value={fmtUsd(data.total_market_value)}
            footnote={!data.priced ? "估值為成本基礎" : undefined}
            degraded={!data.priced}
          />
          <StatCard kicker="持倉檔數" value={data.positions.length} unit="檔" />
        </div>
        {data.theme_exposure.length > 0 ? (
          <div className="mt-4">
            <StackedExposureBar
              segments={data.theme_exposure.map((row) => ({
                label: themeLabel(row.theme),
                pct: row.weightPct,
                theme: row.theme,
              }))}
            />
          </div>
        ) : (
          <p className="mt-4 font-sans text-meta text-ink-faint">尚無主題曝險資料</p>
        )}
        <SourceTag
          source={data.source}
          asOf={data.as_of || undefined}
          degraded={!data.priced}
          className="mt-3"
        />
      </>
    );
  } catch {
    return <Pending />;
  }
}

type SignalRow = {
  ticker: string;
  quarter_label: string;
  score: number;
  rating: string;
  conviction: string;
  report_id: string;
};

async function loadSignalItems(): Promise<SignalRow[] | null> {
  try {
    const since = new Date();
    since.setUTCDate(since.getUTCDate() - 30);
    const rows = await listEarningsSince(since, { limit: 80, maxTier: 5 });

    return rows
      .filter((r) => r.investment_signal?.score != null)
      .map((r) => {
        const sig = r.investment_signal!;
        return {
          report_id: r.report_id,
          ticker: r.ticker,
          quarter_label: r.quarter_label,
          score: sig.score as number,
          rating: sig.rating,
          conviction: sig.conviction,
        };
      })
      .sort((a, b) => b.score - a.score);
  } catch {
    return null;
  }
}

async function SignalsSection() {
  const items = await loadSignalItems();
  if (!items) return <Pending />;

  const buys = items.filter((i) => i.score >= 60).slice(0, 3);
  const avoids = [...items]
    .filter((i) => i.score < 45)
    .reverse()
    .slice(0, 3);

  if (!buys.length && !avoids.length) {
    return <Pending note="尚無含 investment_signal 的近期財報" />;
  }

  const columns: DataColumn<SignalRow>[] = [
    {
      key: "ticker",
      header: "代號",
      render: (row) => (
        <Link href={`/earnings/${row.ticker}`} className="font-semibold text-ink hover:text-accent">
          {row.ticker}
        </Link>
      ),
    },
    { key: "quarter_label", header: "季度" },
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
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <p className="mb-2 font-sans text-meta font-semibold uppercase tracking-wide text-ink-faint">
          Top 買進
        </p>
        {buys.length ? (
          <DataTable columns={columns} rows={buys} rowKey={(r) => r.report_id} />
        ) : (
          <Pending note="本期無 score ≥ 60" />
        )}
      </div>
      <div>
        <p className="mb-2 font-sans text-meta font-semibold uppercase tracking-wide text-ink-faint">
          Top 迴避
        </p>
        {avoids.length ? (
          <DataTable columns={columns} rows={avoids} rowKey={(r) => r.report_id} />
        ) : (
          <Pending note="本期無 score &lt; 45" />
        )}
      </div>
    </div>
  );
}

async function EarningsSection() {
  try {
    const [upcoming, recentSince] = await Promise.all([
      loadUpcomingEarnings(7),
      (async () => {
        const since = new Date();
        since.setUTCDate(since.getUTCDate() - 7);
        return listEarningsSince(since, { limit: 5, maxTier: 5 });
      })(),
    ]);

    type CalRow = { ticker: string; date: string; note: string };
    const upcomingRows: CalRow[] = upcoming.items.slice(0, 5).map((item) => ({
      ticker: item.symbol,
      date: item.next_earnings_date,
      note: `${item.days_until} 日後 · ${item.pillar}`,
    }));

    type RecentRow = { ticker: string; quarter: string; report_id: string };
    const recentRows: RecentRow[] = recentSince.map((r) => ({
      ticker: r.ticker,
      quarter: r.quarter_label,
      report_id: r.report_id,
    }));

    const upcomingCols: DataColumn<CalRow>[] = [
      {
        key: "ticker",
        header: "代號",
        render: (row) => (
          <Link href={`/earnings/${row.ticker}`} className="font-semibold hover:text-accent">
            {row.ticker}
          </Link>
        ),
      },
      { key: "date", header: "日期" },
      { key: "note", header: "備註" },
    ];

    const recentCols: DataColumn<RecentRow>[] = [
      {
        key: "ticker",
        header: "代號",
        render: (row) => (
          <Link href={`/earnings/${row.ticker}`} className="font-semibold hover:text-accent">
            {row.ticker}
          </Link>
        ),
      },
      {
        key: "quarter",
        header: "季度",
        render: (row) => (
          <Link
            href={`/earnings/report/${encodeURIComponent(row.report_id)}`}
            className="hover:text-accent hover:underline"
          >
            {row.quarter}
          </Link>
        ),
      },
    ];

    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <p className="mb-2 font-sans text-meta font-semibold uppercase tracking-wide text-ink-faint">
            未來 7 日
          </p>
          {upcomingRows.length ? (
            <DataTable columns={upcomingCols} rows={upcomingRows} rowKey={(r) => r.ticker + r.date} />
          ) : (
            <Pending note="尚無行事曆資料" />
          )}
        </div>
        <div>
          <p className="mb-2 font-sans text-meta font-semibold uppercase tracking-wide text-ink-faint">
            剛公布
          </p>
          {recentRows.length ? (
            <DataTable columns={recentCols} rows={recentRows} rowKey={(r) => r.report_id} />
          ) : (
            <Pending note="近 7 日無新申報" />
          )}
        </div>
      </div>
    );
  } catch {
    return <Pending />;
  }
}

async function MacroSection() {
  try {
    const snapshot = loadMacroContextSnapshot();
    if (!snapshot?.theme_bias) return <Pending note="尚無 macro_context" />;

    const payload = await buildPortfolioPayload();
    if (!payload.theme_exposure.length) return <Pending note="尚無持倉主題曝險" />;

    const envRows = portfolioEnvironment(payload.theme_exposure, snapshot.theme_bias);
    const weighted = weightedEnvironmentBias(envRows);

    return (
      <>
        <div className="grid gap-4 sm:grid-cols-2">
          <StatCard
            kicker="持倉加權環境"
            value={weighted.label}
            footnote={`加權分數 ${weighted.score.toFixed(2)}`}
          />
          <StatCard
            kicker="宏觀快照"
            value={snapshot.as_of?.slice(0, 10) ?? "—"}
            source="macro_context_latest.json"
          />
        </div>
        <div className="mt-4">
          <DataTable
            columns={[
              {
                key: "theme",
                header: "主題",
                render: (row) => themeLabel(row.theme),
              },
              {
                key: "weight_pct",
                header: "權重%",
                numeric: true,
                render: (row) => `${row.weight_pct.toFixed(1)}%`,
              },
              { key: "bias", header: "傾向" },
            ]}
            rows={envRows.slice(0, 5)}
            rowKey={(row) => row.theme}
          />
        </div>
      </>
    );
  } catch {
    return <Pending />;
  }
}

function CalibrationSection() {
  try {
    const summary = loadBacktestSummary();
    if (!summary) return <Pending note="尚無回測結果" />;

    const horizons = summary.horizons?.length
      ? summary.horizons
      : Object.keys(summary.quantile_spread || {}).map(Number);
    const h = horizons[0];
    if (h == null) return <Pending note="回測摘要缺少 horizon" />;

    const hKey = String(h);
    const ic = summary.ic?.[hKey]?.spearman;
    const icN = summary.ic?.[hKey]?.n ?? 0;
    const hit = summary.hit_rate?.[hKey]?.rate;
    const hitN = summary.hit_rate?.[hKey]?.n ?? 0;
    const spread = summary.quantile_spread?.[hKey]?.spread_pct;

    return (
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          kicker={`命中率（${h} 日）`}
          value={hit != null ? `${(hit * 100).toFixed(0)}%` : "—"}
          footnote={`n=${hitN}`}
        />
        <StatCard
          kicker={`IC Spearman（${h} 日）`}
          value={ic != null ? ic.toFixed(3) : "—"}
          footnote={`n=${icN}`}
        />
        <StatCard
          kicker="分位價差"
          value={
            spread != null && Number.isFinite(spread)
              ? `${spread > 0 ? "+" : ""}${spread.toFixed(2)}%`
              : "—"
          }
          footnote={`樣本 ${summary.n_records ?? "—"} 筆`}
        />
      </div>
    );
  } catch {
    return <Pending />;
  }
}

export default function InvestPage() {
  return (
    <DensePageShell
      kicker="Invest Hub"
      title="投資中樞"
      description="持倉、訊號、財報、宏觀與校驗的一頁摘要。各區塊連至完整細節頁。非投資建議。"
    >
      <SectionBand title="我的持倉概況" moreHref="/portfolio" moreLabel="查看持倉 →">
        <PortfolioSection />
      </SectionBand>

      <SectionBand title="本期訊號" moreHref="/signals" moreLabel="完整排行 →">
        <SignalsSection />
      </SectionBand>

      <SectionBand title="近期財報" moreHref="/earnings" moreLabel="財報全覽 →">
        <EarningsSection />
      </SectionBand>

      <SectionBand title="宏觀與供應鏈傾向" moreHref="/macro" moreLabel="宏觀詳情 →">
        <MacroSection />
      </SectionBand>

      <SectionBand title="訊號校驗摘要" moreHref="/calibration" moreLabel="校驗詳情 →">
        <CalibrationSection />
      </SectionBand>
    </DensePageShell>
  );
}
