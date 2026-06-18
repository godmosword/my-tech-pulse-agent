"use client";

import dynamic from "next/dynamic";

/**
 * Client-only dynamic wrapper so recharts is not bundled into the report route's
 * initial payload (it only renders when a report actually has trend data).
 * `ssr: false` is valid only inside a client component, hence this wrapper.
 */
export const EarningsTrendChart = dynamic(
  () => import("./EarningsTrendChart").then((m) => m.EarningsTrendChart),
  {
    ssr: false,
    loading: () => (
      <div
        className="h-40 w-full motion-safe:animate-pulse rounded bg-[var(--color-rule)]/30"
        role="status"
        aria-busy="true"
        aria-label="趨勢圖載入中"
      />
    ),
  },
);
