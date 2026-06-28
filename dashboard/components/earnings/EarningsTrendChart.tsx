"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  EarningsTrendRow,
  MetricTrendRow,
  QuarterPointRow,
} from "@/lib/earnings-firestore";
import { fmtNum, fmtPctSigned } from "@/lib/format-numbers";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import {
  AXIS_TICK,
  GRID_STROKE,
  TOOLTIP_CONTENT_STYLE,
  TOOLTIP_ITEM_STYLE,
  TOOLTIP_LABEL_STYLE,
} from "@/components/data/chart-theme";

const DIRECTION_CLASS: Record<string, string> = {
  擴張: "text-pos",
  收縮: "text-neg",
  持平: "text-ink-soft",
  資料不足: "text-ink-faint",
};

export interface TrendChartPoint {
  name: string;
  value: number;
}

function periodLabel(p: QuarterPointRow): string {
  return `${p.fiscal_year ?? ""} ${p.fiscal_period}`.trim();
}

/** Pure transform: numeric points oldest→newest, ready for the line chart. */
export function metricChartData(trend: MetricTrendRow): TrendChartPoint[] {
  return trend.points
    .filter((p): p is QuarterPointRow & { value: number } => p.value != null)
    .map((p) => ({ name: periodLabel(p), value: p.value }));
}

function MetricTrendRowChart({ trend }: { trend: MetricTrendRow }) {
  const reduced = useReducedMotion();
  const data = metricChartData(trend);
  if (data.length < 2) return null; // too sparse to draw a meaningful line

  const directionClass = DIRECTION_CLASS[trend.direction] ?? "text-ink-faint";
  const label = trend.label_zh || trend.metric;

  return (
    <div className="section-band">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-sans text-meta font-semibold uppercase tracking-[0.08em] text-ink-soft">
          {label}
        </p>
        <p className="font-sans text-meta">
          <span className={directionClass}>{trend.direction}</span>
          {trend.yoy_pct != null && (
            <span className="ml-2 text-ink-faint">
              YoY <span className="data-num">{fmtPctSigned(trend.yoy_pct)}</span>
            </span>
          )}
          {trend.qoq_pct != null && (
            <span className="ml-2 text-ink-faint">
              QoQ <span className="data-num">{fmtPctSigned(trend.qoq_pct)}</span>
            </span>
          )}
        </p>
      </div>
      <div
        className="h-40 w-full"
        role="img"
        aria-label={`${label} 多季趨勢，${trend.direction}，共 ${data.length} 季`}
      >
        <ResponsiveContainer width="100%" height="100%" aria-hidden>
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis
              dataKey="name"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: GRID_STROKE }}
            />
            <YAxis
              width={48}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => fmtNum(v)}
            />
            <Tooltip
              contentStyle={TOOLTIP_CONTENT_STYLE}
              labelStyle={TOOLTIP_LABEL_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              formatter={(v: number) => [fmtNum(v), label]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--chart-4)"
              strokeWidth={2}
              dot={{ r: 2 }}
              isAnimationActive={!reduced}
              animationDuration={560}
              animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/**
 * Multi-quarter trend for a single earnings report. Renders one sparkline per
 * tracked metric; metrics with fewer than two numeric quarters are skipped, and
 * the whole block renders nothing when no metric has enough data.
 */
export function EarningsTrendChart({ trend }: { trend: EarningsTrendRow }) {
  const drawable = trend.trends.filter((t) => metricChartData(t).length >= 2);
  if (drawable.length === 0) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {drawable.map((t) => (
        <MetricTrendRowChart key={t.metric} trend={t} />
      ))}
    </div>
  );
}
