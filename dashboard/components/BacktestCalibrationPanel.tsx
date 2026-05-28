import type { BacktestSummary } from "@/lib/backtest-data";

const RATING_ORDER = ["強力看多", "看多", "中性", "看空", "強力看空", "資料不足"];

type Props = {
  summary: BacktestSummary;
  title: string;
};

function fmtPct(v: number | null | undefined): string {
  if (v === undefined || v === null || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function Bar({ value, maxAbs }: { value: number; maxAbs: number }) {
  const width = maxAbs > 0 ? Math.min(100, (Math.abs(value) / maxAbs) * 100) : 0;
  const positive = value >= 0;
  return (
    <div className="flex h-5 flex-1 items-center">
      <div
        className={`h-3 rounded-sm ${positive ? "bg-emerald-500/70" : "bg-rose-500/70"}`}
        style={{ width: `${width}%`, minWidth: value !== 0 ? "4px" : 0 }}
      />
    </div>
  );
}

export function BacktestCalibrationPanel({ summary, title }: Props) {
  const horizons = summary.horizons?.length
    ? summary.horizons
    : Object.keys(summary.quantile_spread || {}).map(Number);

  return (
    <section className="mt-8">
      <h2 className="font-serif text-xl font-semibold text-ink">{title}</h2>
      <p className="mt-1 font-sans text-meta text-ink-faint">
        樣本 {summary.n_records ?? "—"} 筆 · horizons {horizons.join(" / ")} 交易日
      </p>

      {horizons.map((h) => {
        const hKey = String(h);
        const q = summary.quantile_spread?.[hKey];
        const top = q?.top_tertile_mean_excess_pct ?? 0;
        const bot = q?.bottom_tertile_mean_excess_pct ?? 0;
        const maxAbs = Math.max(Math.abs(top), Math.abs(bot), 0.01);
        const ic = summary.ic?.[hKey]?.spearman;
        const icN = summary.ic?.[hKey]?.n ?? 0;
        const buckets = summary.by_rating?.[hKey] ?? {};

        return (
          <div key={h} className="mt-8">
            <h3 className="font-sans text-body font-semibold text-ink">{h} 交易日</h3>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-rule p-4">
                <p className="font-sans text-meta text-ink-faint">分位數價差（高 − 低）</p>
                <p className="mt-1 font-mono text-2xl tabular-nums text-ink">
                  {fmtPct(q?.spread_pct)}
                </p>
              </div>
              <div className="rounded-lg border border-rule p-4">
                <p className="font-sans text-meta text-ink-faint">IC（Spearman）</p>
                <p className="mt-1 font-mono text-2xl tabular-nums text-ink">
                  {ic != null ? ic.toFixed(3) : "—"}
                  <span className="ml-2 font-sans text-meta text-ink-faint">n={icN}</span>
                </p>
              </div>
            </div>

            <div className="mt-6 space-y-3">
              <p className="font-sans text-meta font-semibold uppercase tracking-wide text-ink-faint">
                高分組 vs 低分組 平均超額（vs SOXX）
              </p>
              <div className="flex items-center gap-3 font-sans text-body">
                <span className="w-24 shrink-0 text-ink-soft">Top 1/3</span>
                <Bar value={top} maxAbs={maxAbs} />
                <span className="w-16 shrink-0 text-right font-mono tabular-nums">{fmtPct(top)}</span>
              </div>
              <div className="flex items-center gap-3 font-sans text-body">
                <span className="w-24 shrink-0 text-ink-soft">Bottom 1/3</span>
                <Bar value={bot} maxAbs={maxAbs} />
                <span className="w-16 shrink-0 text-right font-mono tabular-nums">{fmtPct(bot)}</span>
              </div>
            </div>

            <div className="mt-6 overflow-x-auto">
              <table className="w-full min-w-[480px] font-sans text-body">
                <thead>
                  <tr className="border-b border-rule text-left text-meta text-ink-faint">
                    <th className="pb-2 pr-4 font-normal">評級</th>
                    <th className="pb-2 pr-4 font-normal">n</th>
                    <th className="pb-2 pr-4 font-normal">平均超額</th>
                    <th className="pb-2 font-normal">勝率</th>
                  </tr>
                </thead>
                <tbody>
                  {RATING_ORDER.filter((r) => buckets[r]).map((rating) => {
                    const b = buckets[rating];
                    return (
                      <tr key={rating} className="border-b border-rule/60">
                        <td className="py-2 pr-4">
                          {rating}
                          {b.insufficient_sample && (
                            <span className="ml-1 text-meta text-rose-600">⚠</span>
                          )}
                        </td>
                        <td className="py-2 pr-4 font-mono tabular-nums">{b.n}</td>
                        <td className="py-2 pr-4 font-mono tabular-nums">
                          {fmtPct(b.mean_excess_pct)}
                        </td>
                        <td className="py-2 font-mono tabular-nums">
                          {b.win_rate != null ? `${(b.win_rate * 100).toFixed(0)}%` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </section>
  );
}
