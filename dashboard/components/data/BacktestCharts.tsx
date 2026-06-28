"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BacktestSummary } from "@/lib/backtest-data";
import { fmtPctSigned } from "@/lib/format-numbers";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import {
  AXIS_TICK,
  GRID_STROKE,
  TOOLTIP_CONTENT_STYLE,
  TOOLTIP_ITEM_STYLE,
  TOOLTIP_LABEL_STYLE,
} from "./chart-theme";

type Props = {
  summary: BacktestSummary;
  horizonKey: string;
  topMean: number;
  bottomMean: number;
};

export function BacktestQuantileChart({ topMean, bottomMean }: Omit<Props, "summary" | "horizonKey">) {
  const reduced = useReducedMotion();
  const data = [
    { name: "Top 1/3", value: topMean },
    { name: "Bottom 1/3", value: bottomMean },
  ];

  return (
    <div
      className="h-48 w-full"
      role="img"
      aria-label={`分位價差：Top 1/3 平均超額 ${fmtPctSigned(topMean)}，Bottom 1/3 平均超額 ${fmtPctSigned(bottomMean)}`}
    >
      <ResponsiveContainer width="100%" height="100%" aria-hidden>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis
            dataKey="name"
            tick={AXIS_TICK}
            axisLine={{ stroke: GRID_STROKE }}
            tickLine={false}
          />
          <YAxis
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            formatter={(v: number) => [fmtPctSigned(v), "平均超額"]}
            contentStyle={TOOLTIP_CONTENT_STYLE}
            labelStyle={TOOLTIP_LABEL_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={!reduced}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={entry.value >= 0 ? "var(--color-pos)" : "var(--color-neg)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const RATING_ORDER = ["強力看多", "看多", "中性", "看空", "強力看空", "資料不足"];

function ratingColor(rating: string, mean: number | null | undefined): string {
  if (rating.includes("看多")) return "var(--color-pos)";
  if (rating.includes("看空")) return "var(--color-neg)";
  if (mean != null && mean > 0) return "var(--color-pos)";
  if (mean != null && mean < 0) return "var(--color-neg)";
  return "var(--color-info)";
}

export function BacktestCalibrationChart({
  summary,
  horizonKey,
}: Pick<Props, "summary" | "horizonKey">) {
  const reduced = useReducedMotion();
  const buckets = summary.by_rating?.[horizonKey] ?? {};
  const data = RATING_ORDER.filter((r) => buckets[r]).map((rating) => ({
    rating,
    mean: buckets[rating].mean_excess_pct ?? 0,
    n: buckets[rating].n,
  }));

  if (data.length === 0) return null;

  const chartLabel = data
    .map((entry) => `${entry.rating} 平均超額 ${fmtPctSigned(entry.mean)}（n=${entry.n}）`)
    .join("；");

  return (
    <div className="mt-4">
      <p className="mb-2 font-sans text-meta font-semibold uppercase tracking-wide text-ink-faint">
        校準曲線（各評級平均超額 vs SOXX）
      </p>
      <div
        className="h-56 w-full"
        role="img"
        aria-label={`校準曲線：${chartLabel}`}
      >
        <ResponsiveContainer width="100%" height="100%" aria-hidden>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 24 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis
              dataKey="rating"
              tick={AXIS_TICK}
              axisLine={{ stroke: GRID_STROKE }}
              tickLine={false}
              interval={0}
              angle={-20}
              textAnchor="end"
              height={48}
            />
            <YAxis
              tick={AXIS_TICK}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              formatter={(v: number, _n, item) => {
                const payload = item.payload as { n: number };
                return [fmtPctSigned(v), `n=${payload.n}`];
              }}
              contentStyle={TOOLTIP_CONTENT_STYLE}
              labelStyle={TOOLTIP_LABEL_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
            />
            <Bar dataKey="mean" radius={[4, 4, 0, 0]} isAnimationActive={!reduced}>
              {data.map((entry) => (
                <Cell
                  key={entry.rating}
                  fill={ratingColor(entry.rating, entry.mean)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
