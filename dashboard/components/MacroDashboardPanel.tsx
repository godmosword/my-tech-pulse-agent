import type { MacroContextSnapshot } from "@/lib/macro-data";
import { THEME_LABELS } from "@/lib/macro-data";
import type { PortfolioEnvironmentRow } from "@/lib/portfolio-metrics";

type Props = {
  snapshot: MacroContextSnapshot;
  portfolioEnv?: PortfolioEnvironmentRow[];
  weightedBias?: { label: string; score: number };
};

function trendClass(trend?: string): string {
  if (trend === "上升" || trend === "加速") return "text-emerald-600 dark:text-emerald-400";
  if (trend === "下降" || trend === "放緩") return "text-rose-600 dark:text-rose-400";
  return "text-ink-soft";
}

function biasClass(bias: string): string {
  if (bias === "順風") return "text-emerald-700 dark:text-emerald-300";
  if (bias === "逆風") return "text-rose-700 dark:text-rose-300";
  return "text-ink-soft";
}

function MiniBar({ value, max }: { value: number; max: number }) {
  const w = max > 0 ? Math.min(100, (Math.abs(value) / max) * 100) : 0;
  const positive = value >= 0;
  return (
    <div className="h-2 flex-1 rounded bg-rule/40">
      <div
        className={`h-2 rounded ${positive ? "bg-emerald-500/80" : "bg-rose-500/80"}`}
        style={{ width: `${w}%` }}
      />
    </div>
  );
}

export function MacroDashboardPanel({ snapshot, portfolioEnv, weightedBias }: Props) {
  const macro = snapshot.macro ?? {};
  const sc = snapshot.supply_chain ?? {};
  const themes = snapshot.theme_bias ?? {};

  const tsmYoy = sc.tsm?.yoy_pct ?? 0;
  const maxBar = Math.max(Math.abs(tsmYoy), 1);

  return (
    <div className="space-y-10">
      <section>
        <h2 className="font-serif text-xl font-semibold text-ink">宏觀儀表</h2>
        <p className="mt-1 font-sans text-meta text-ink-faint">
          as_of {snapshot.as_of?.slice(0, 10) ?? "—"}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {(["fed_funds_rate", "cpi_yoy", "treasury_10y"] as const).map((key) => {
            const m = macro[key];
            if (!m) return null;
            const label =
              key === "fed_funds_rate"
                ? "聯邦基金利率"
                : key === "cpi_yoy"
                  ? "CPI YoY"
                  : "10Y 公債";
            const unit = key === "cpi_yoy" ? "%" : "%";
            return (
              <div key={key} className="rounded-lg border border-rule p-4">
                <p className="font-sans text-meta text-ink-faint">{label}</p>
                <p className="mt-1 font-mono text-2xl tabular-nums text-ink">
                  {m.value}
                  {unit}
                </p>
                <p className={`mt-1 font-sans text-meta ${trendClass(m.trend)}`}>
                  {m.trend ?? "—"} · {m.date ?? ""}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="font-serif text-xl font-semibold text-ink">供應鏈</h2>
        <div className="mt-4 grid gap-6 lg:grid-cols-2">
          <div className="rounded-lg border border-rule p-4">
            <p className="font-sans text-meta text-ink-faint">TSM 月營收 YoY</p>
            {sc.tsm?.latest_month ? (
              <>
                <p className="mt-1 font-mono text-xl tabular-nums">
                  {sc.tsm.yoy_pct != null ? `${sc.tsm.yoy_pct > 0 ? "+" : ""}${sc.tsm.yoy_pct}%` : "—"}
                  <span className="ml-2 font-sans text-meta text-ink-faint">
                    {sc.tsm.latest_month}
                  </span>
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <MiniBar value={tsmYoy} max={maxBar} />
                </div>
                <p className="mt-2 font-sans text-meta text-ink-faint">
                  來源：{sc.tsm.source ?? "—"} · 趨勢 {sc.tsm.trend ?? "—"}
                </p>
              </>
            ) : (
              <p className="mt-2 font-sans text-body text-ink-faint">尚無 TSM 資料</p>
            )}
          </div>
          <div className="rounded-lg border border-rule p-4">
            <p className="font-sans text-meta text-ink-faint">SIA 全球半導體銷售</p>
            {sc.sia?.latest_month ? (
              <>
                <p className="mt-1 font-mono text-xl tabular-nums">
                  {sc.sia.sales_usd_b != null ? `$${sc.sia.sales_usd_b}B` : "—"}
                  {sc.sia.yoy_pct != null && (
                    <span className="ml-2 text-body">
                      YoY {sc.sia.yoy_pct > 0 ? "+" : ""}
                      {sc.sia.yoy_pct}%
                    </span>
                  )}
                </p>
                <p className="mt-2 font-sans text-meta text-ink-faint">
                  {sc.sia.source === "manual" && sc.sia.as_of
                    ? `人工維護，as_of ${sc.sia.as_of}`
                    : `來源 ${sc.sia.source ?? "—"}`}
                </p>
              </>
            ) : (
              <p className="mt-2 font-sans text-body text-ink-faint">尚無 SIA 資料</p>
            )}
            {sc.asml?.bookings_eur_b != null && (
              <p className="mt-4 font-sans text-body text-ink-soft">
                ASML {sc.asml.quarter} bookings {sc.asml.bookings_eur_b}B EUR（
                {sc.asml.source === "manual" ? `人工維護 as_of ${sc.asml.as_of}` : "—"}）
              </p>
            )}
          </div>
        </div>
      </section>

      <section>
        <h2 className="font-serif text-xl font-semibold text-ink">主題環境</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[520px] font-sans text-body">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-faint">
                <th className="pb-2 pr-4 font-normal">主題</th>
                <th className="pb-2 pr-4 font-normal">傾向</th>
                <th className="pb-2 font-normal">數據理由</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(themes).map(([theme, row]) => (
                <tr key={theme} className="border-b border-rule/60 align-top">
                  <td className="py-3 pr-4">{THEME_LABELS[theme] ?? theme}</td>
                  <td className={`py-3 pr-4 font-medium ${biasClass(row.bias)}`}>
                    {row.bias}
                  </td>
                  <td className="py-3 text-meta text-ink-soft">
                    {(row.drivers_zh ?? []).join("；") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {portfolioEnv && portfolioEnv.length > 0 && (
        <section>
          <h2 className="font-serif text-xl font-semibold text-ink">持倉加權環境</h2>
          {weightedBias && weightedBias.label !== "—" && (
            <p className="mt-2 font-sans text-body text-ink-soft">
              整體曝險傾向：
              <span className={`ml-1 font-medium ${biasClass(weightedBias.label)}`}>
                {weightedBias.label}
              </span>
            </p>
          )}
          <ul className="mt-4 space-y-2 font-sans text-body">
            {portfolioEnv.slice(0, 6).map((row) => (
              <li key={row.theme} className="rounded border border-rule/60 p-3">
                <span className="font-medium text-ink">
                  {THEME_LABELS[row.theme] ?? row.theme}
                </span>{" "}
                <span className="text-ink-faint">{row.weight_pct.toFixed(1)}%</span>
                {row.bias !== "—" && (
                  <span className={`ml-2 ${biasClass(row.bias)}`}>· {row.bias}</span>
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
