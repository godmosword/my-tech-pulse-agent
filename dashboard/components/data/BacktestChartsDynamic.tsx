"use client";

import dynamic from "next/dynamic";

/**
 * Client-only dynamic wrappers for the recharts-based backtest charts. recharts
 * is heavy and only appears on `/calibration`; loading it with `ssr: false`
 * keeps it out of the route's initial server-rendered payload and defers the
 * chunk to the client. `ssr: false` is only valid inside a client component,
 * which is why this wrapper exists — the server `BacktestCalibrationPanel`
 * imports from here instead of importing recharts directly.
 */

function ChartFallback({ className }: { className: string }) {
  return (
    <div
      className={`${className} motion-safe:animate-pulse rounded bg-[var(--color-rule)]/30`}
      role="status"
      aria-busy="true"
      aria-label="圖表載入中"
    />
  );
}

export const BacktestQuantileChart = dynamic(
  () => import("./BacktestCharts").then((m) => m.BacktestQuantileChart),
  { ssr: false, loading: () => <ChartFallback className="h-48 w-full" /> },
);

export const BacktestCalibrationChart = dynamic(
  () => import("./BacktestCharts").then((m) => m.BacktestCalibrationChart),
  { ssr: false, loading: () => <ChartFallback className="h-56 w-full" /> },
);
