import type { MacroContextSnapshot } from "@/lib/macro-data";
import { THEME_LABELS } from "@/lib/macro-data";
import type { PortfolioEnvironmentRow } from "@/lib/portfolio-metrics";

import { DataTable, type DataColumn } from "@/components/data/DataTable";
import { Delta } from "@/components/data/Delta";
import { SourceTag } from "@/components/data/SourceTag";
import { StackedExposureBar } from "@/components/data/StackedExposureBar";
import { StatCard } from "@/components/data/StatCard";

type Props = {
  snapshot: MacroContextSnapshot;
  portfolioEnv?: PortfolioEnvironmentRow[];
  weightedBias?: { label: string; score: number };
};

function biasClass(bias: string): string {
  if (bias === "順風") return "text-pos";
  if (bias === "逆風") return "text-neg";
  return "text-info";
}

type ThemeRow = { theme: string; bias: string; drivers: string };

export function MacroDashboardPanel({ snapshot, portfolioEnv, weightedBias }: Props) {
  const macro = snapshot.macro ?? {};
  const sc = snapshot.supply_chain ?? {};
  const themes = snapshot.theme_bias ?? {};

  const themeRows: ThemeRow[] = Object.entries(themes).map(([theme, row]) => ({
    theme: THEME_LABELS[theme] ?? theme,
    bias: row.bias,
    drivers: (row.drivers_zh ?? []).join("；") || "—",
  }));

  const themeColumns: DataColumn<ThemeRow>[] = [
    { key: "theme", header: "主題", align: "left" },
    {
      key: "bias",
      header: "傾向",
      render: (row) => <span className={`font-semibold ${biasClass(row.bias)}`}>{row.bias}</span>,
    },
    { key: "drivers", header: "數據理由", align: "left" },
  ];

  return (
    <div className="dense space-y-8">
      <section className="section-band">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-sans text-lg font-semibold text-ink">宏觀儀表</h2>
          <SourceTag asOf={snapshot.as_of?.slice(0, 10)} source="FRED" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(["fed_funds_rate", "cpi_yoy", "treasury_10y"] as const).map((key) => {
            const m = macro[key];
            if (!m) return null;
            const label =
              key === "fed_funds_rate"
                ? "聯邦基金利率"
                : key === "cpi_yoy"
                  ? "CPI YoY"
                  : "10Y 公債";
            return (
              <StatCard
                key={key}
                kicker={label}
                value={m.value ?? "—"}
                unit="%"
                footnote={`${m.trend ?? "—"} · ${m.date ?? ""}`}
                source="FRED"
              />
            );
          })}
        </div>
      </section>

      <section className="section-band">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-sans text-lg font-semibold text-ink">供應鏈</h2>
          <SourceTag source="TWSE / manual" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <StatCard
            kicker="TSM 月營收 YoY"
            value={
              sc.tsm?.yoy_pct != null
                ? `${sc.tsm.yoy_pct > 0 ? "+" : ""}${sc.tsm.yoy_pct}`
                : "—"
            }
            unit={sc.tsm?.yoy_pct != null ? "%" : undefined}
            footnote={
              sc.tsm?.latest_month
                ? `${sc.tsm.latest_month} · 趨勢 ${sc.tsm.trend ?? "—"} · ${sc.tsm.source ?? ""}`
                : "尚無 TSM 資料"
            }
            source={sc.tsm?.source}
          />
          <StatCard
            kicker="SIA 全球半導體銷售"
            value={sc.sia?.sales_usd_b != null ? sc.sia.sales_usd_b : "—"}
            unit={sc.sia?.sales_usd_b != null ? "B USD" : undefined}
            delta={sc.sia?.yoy_pct ?? undefined}
            footnote={sc.sia?.latest_month ? `月份 ${sc.sia.latest_month}` : "尚無 SIA 資料"}
            source={sc.sia?.source}
            asOf={sc.sia?.as_of}
            manual={sc.sia?.source === "manual"}
          />
        </div>
        {sc.tsm?.yoy_pct != null && (
          <div className="mt-4">
            <p className="mb-2 font-sans text-meta text-ink-faint">TSM YoY 方向</p>
            <Delta value={sc.tsm.yoy_pct} showArrow={false} />
          </div>
        )}
        {sc.asml?.bookings_eur_b != null && (
          <p className="mt-4 font-sans text-body text-ink-soft">
            ASML {sc.asml.quarter} bookings {sc.asml.bookings_eur_b}B EUR
            {sc.asml.source === "manual" && sc.asml.as_of && (
              <SourceTag manual asOf={sc.asml.as_of} className="ml-2" />
            )}
          </p>
        )}
      </section>

      <section className="section-band">
        <h2 className="font-sans text-lg font-semibold text-ink">主題環境</h2>
        <div className="mt-4">
          <DataTable columns={themeColumns} rows={themeRows} rowKey={(row) => row.theme} />
        </div>
      </section>

      {portfolioEnv && portfolioEnv.length > 0 && (
        <section className="section-band">
          <h2 className="font-sans text-lg font-semibold text-ink">持倉加權環境</h2>
          {weightedBias && weightedBias.label !== "—" && (
            <p className="mt-2 font-sans text-body text-ink-soft">
              整體曝險傾向：
              <span className={`ml-1 font-semibold ${biasClass(weightedBias.label)}`}>
                {weightedBias.label}
              </span>
            </p>
          )}
          <div className="mt-4">
            <StackedExposureBar
              segments={portfolioEnv.slice(0, 8).map((row) => ({
                label: THEME_LABELS[row.theme] ?? row.theme,
                pct: row.weight_pct,
                theme: row.theme,
              }))}
            />
          </div>
          <ul className="mt-4 space-y-2">
            {portfolioEnv.slice(0, 6).map((row) => (
              <li key={row.theme} className="rounded border border-rule/60 p-3 font-sans text-body">
                <span className="font-medium text-ink">{THEME_LABELS[row.theme] ?? row.theme}</span>
                <span className="data-num ml-2 text-ink-faint">{row.weight_pct.toFixed(1)}%</span>
                {row.bias !== "—" && (
                  <span className={`ml-2 font-semibold ${biasClass(row.bias)}`}>· {row.bias}</span>
                )}
                {row.drivers_zh.length > 0 && (
                  <p className="mt-1 text-meta text-ink-soft">{row.drivers_zh[0]}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
