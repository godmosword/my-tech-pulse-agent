import type { Metadata } from "next";

import { Hairline } from "@/components/Hairline";
import { Kicker } from "@/components/Kicker";
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

function tierBadge(tier: string) {
  const base =
    "rounded border px-2 py-0.5 font-mono text-meta uppercase tracking-wide";
  if (tier === "holding") {
    return (
      <span className={`${base} border-accent/40 bg-accent/10 text-accent`}>
        持倉
      </span>
    );
  }
  if (tier === "watchlist") {
    return (
      <span className={`${base} border-rule text-ink-soft`}>觀察</span>
    );
  }
  return (
    <span className={`${base} border-rule text-ink-faint`}>其他</span>
  );
}

function rebalanceHint(driftPct: number): string {
  if (driftPct > 2) return "超配 — 可考慮減碼或再平衡（僅提示）";
  if (driftPct < -2) return "低配 — 可考慮補倉或再平衡（僅提示）";
  return "接近目標";
}

export default async function PortfolioPage() {
  const data = await buildPortfolioPayload();
  const topTheme = data.theme_exposure[0];
  const themeAlert = topTheme && topTheme.weightPct > 50;

  return (
    <div>
      <Kicker tone="accent">Portfolio</Kicker>
      <h1 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-ink">
        持倉總覽
      </h1>
      <p className="mt-3 max-w-prose font-sans text-body text-ink-soft">
        資料截至 {data.as_of || "—"} · 來源 {data.source}
        {!data.priced && (
          <span className="ml-2 text-amber-700 dark:text-amber-400">
            （估值為成本基礎 — 未取到即時報價）
          </span>
        )}
      </p>
      <p className="mt-1 font-mono text-meta text-ink-faint">
        總市值 {fmtUsd(data.total_market_value)}
      </p>
      <Hairline className="mt-6" />

      <section className="mt-10">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          持倉明細
        </h2>
        {data.positions.length === 0 ? (
          <p className="mt-4 font-sans text-body text-ink-faint">
            尚無持倉。請編輯 <code className="font-mono text-meta">config/portfolio.yaml</code>{" "}
            或執行 <code className="font-mono text-meta">scripts/import_ibkr_portfolio.py</code>。
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse font-sans text-body">
              <thead>
                <tr className="border-b border-rule text-left text-meta uppercase tracking-wide text-ink-faint">
                  <th className="py-2 pr-4">代號</th>
                  <th className="py-2 pr-4">股數</th>
                  <th className="py-2 pr-4">市值</th>
                  <th className="py-2 pr-4">權重%</th>
                  <th className="py-2 pr-4">未實現%</th>
                  <th className="py-2 pr-4">主題</th>
                  <th className="py-2">分層</th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map((row) => (
                  <tr key={row.ticker} className="border-b border-rule/60">
                    <td className="py-3 pr-4 font-mono font-semibold text-ink">
                      {row.ticker}
                    </td>
                    <td className="py-3 pr-4 font-mono text-ink-soft">
                      {row.shares.toLocaleString()}
                    </td>
                    <td className="py-3 pr-4 font-mono text-ink-soft">
                      {fmtUsd(row.market_value)}
                    </td>
                    <td className="py-3 pr-4 font-mono text-ink-soft">
                      {row.weight_pct.toFixed(1)}%
                    </td>
                    <td className="py-3 pr-4 font-mono text-ink-soft">
                      {row.unrealized_pct != null
                        ? `${row.unrealized_pct >= 0 ? "+" : ""}${row.unrealized_pct.toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="py-3 pr-4 font-mono text-meta text-ink-faint">
                      {row.theme}
                    </td>
                    <td className="py-3">{tierBadge(row.tier)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mt-12">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          主題曝險
        </h2>
        {topTheme && (
          <p
            className={`mt-2 font-sans text-body ${
              themeAlert ? "font-semibold text-amber-700 dark:text-amber-400" : "text-ink-soft"
            }`}
          >
            最大集中度：{topTheme.theme} {topTheme.weightPct.toFixed(1)}%
            {themeAlert ? " — 超過 50% 警示" : ""}
          </p>
        )}
        <ul className="mt-4 space-y-3">
          {data.theme_exposure.map((row) => (
            <li key={row.theme}>
              <div className="flex justify-between font-mono text-meta text-ink-soft">
                <span>{row.theme}</span>
                <span>
                  {row.weightPct.toFixed(1)}% · {fmtUsd(row.marketValue)}
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-rule/40">
                <div
                  className={`h-full rounded-full ${
                    themeAlert && row.theme === topTheme?.theme
                      ? "bg-amber-600"
                      : "bg-accent"
                  }`}
                  style={{ width: `${Math.min(100, row.weightPct)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-12">
        <h2 className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          配置漂移
        </h2>
        <p className="mt-2 font-sans text-body text-ink-faint">
          正 drift = 超配；負 drift = 低配（相對目標配置）。
        </p>
        <ul className="mt-4 divide-y divide-rule">
          {data.allocation_drift.map((row) => (
            <li key={row.theme} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
              <span className="font-mono text-body font-semibold text-ink">{row.theme}</span>
              <span className="font-mono text-meta text-ink-soft">
                目前 {row.currentPct.toFixed(1)}% · 目標 {row.targetPct.toFixed(1)}%
              </span>
              <span
                className={`w-full font-sans text-meta ${
                  row.driftPct > 2
                    ? "text-amber-700 dark:text-amber-400"
                    : row.driftPct < -2
                      ? "text-sky-700 dark:text-sky-400"
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
    </div>
  );
}
