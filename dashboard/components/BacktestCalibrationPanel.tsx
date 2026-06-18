import type { BacktestSummary } from "@/lib/backtest-data";
import { fmtPctSigned } from "@/lib/format-numbers";

import {
  BacktestCalibrationChart,
  BacktestQuantileChart,
} from "@/components/data/BacktestChartsDynamic";
import { DataTable, type DataColumn } from "@/components/data/DataTable";
import { SourceTag } from "@/components/data/SourceTag";
import { StatCard } from "@/components/data/StatCard";

const RATING_ORDER = ["強力看多", "看多", "中性", "看空", "強力看空", "資料不足"];

type Props = {
  summary: BacktestSummary;
  title: string;
};

type RatingRow = {
  rating: string;
  n: number;
  mean: string;
  winRate: string;
  warn: boolean;
};

export function BacktestCalibrationPanel({ summary, title }: Props) {
  const horizons = summary.horizons?.length
    ? summary.horizons
    : Object.keys(summary.quantile_spread || {}).map(Number);

  return (
    <section className="dense section-band mt-8">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-sans text-lg font-semibold text-ink">{title}</h2>
          <p className="mt-1 font-sans text-meta text-ink-faint">
            樣本 {summary.n_records ?? "—"} 筆 · horizons {horizons.join(" / ")} 交易日
          </p>
        </div>
        <SourceTag source="backtest/results" />
      </div>

      {horizons.map((h) => {
        const hKey = String(h);
        const q = summary.quantile_spread?.[hKey];
        const top = q?.top_tertile_mean_excess_pct ?? 0;
        const bot = q?.bottom_tertile_mean_excess_pct ?? 0;
        const ic = summary.ic?.[hKey]?.spearman;
        const icN = summary.ic?.[hKey]?.n ?? 0;
        const buckets = summary.by_rating?.[hKey] ?? {};

        const ratingRows: RatingRow[] = RATING_ORDER.filter((r) => buckets[r]).map((rating) => {
          const b = buckets[rating];
          return {
            rating,
            n: b.n,
            mean: fmtPctSigned(b.mean_excess_pct),
            winRate: b.win_rate != null ? `${(b.win_rate * 100).toFixed(0)}%` : "—",
            warn: Boolean(b.insufficient_sample),
          };
        });

        const ratingColumns: DataColumn<RatingRow>[] = [
          {
            key: "rating",
            header: "評級",
            render: (row) => (
              <span>
                {row.rating}
                {row.warn && <span className="ml-1 text-warn">⚠</span>}
              </span>
            ),
          },
          { key: "n", header: "n", numeric: true },
          { key: "mean", header: "平均超額", numeric: true },
          { key: "winRate", header: "勝率", numeric: true },
        ];

        return (
          <div key={h} className="mt-8 border-t border-rule pt-8 first:mt-6 first:border-t-0 first:pt-0">
            <h3 className="font-sans text-body font-semibold text-ink">{h} 交易日</h3>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <StatCard kicker="分位數價差（高 − 低）" value={fmtPctSigned(q?.spread_pct)} />
              <StatCard
                kicker="IC（Spearman）"
                value={ic != null ? ic.toFixed(3) : "—"}
                footnote={`n=${icN}`}
              />
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <div>
                <p className="mb-2 font-sans text-meta font-semibold uppercase tracking-wide text-ink-faint">
                  高分組 vs 低分組
                </p>
                <BacktestQuantileChart topMean={top} bottomMean={bot} />
                <div className="mt-2 flex justify-between font-sans text-meta text-ink-soft">
                  <span>
                    Top: <span className="data-num text-pos">{fmtPctSigned(top)}</span>
                  </span>
                  <span>
                    Bottom: <span className="data-num text-neg">{fmtPctSigned(bot)}</span>
                  </span>
                </div>
              </div>
              <BacktestCalibrationChart summary={summary} horizonKey={hKey} />
            </div>

            <div className="mt-6">
              <DataTable
                columns={ratingColumns}
                rows={ratingRows}
                rowKey={(row) => row.rating}
              />
            </div>
          </div>
        );
      })}
    </section>
  );
}
