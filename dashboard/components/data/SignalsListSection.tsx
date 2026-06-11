"use client";

import { useCallback, useState } from "react";

import { LoadMoreButton } from "@/components/LoadMoreButton";
import { SignalsTable } from "@/components/data/SignalsTable";
import type { PortfolioTier } from "@/lib/portfolio-metrics";

export type SignalTableItem = {
  report_id: string;
  ticker: string;
  quarter_label: string;
  score: number;
  rating: string;
  conviction: string;
  top_factor: string;
  portfolio_tier: PortfolioTier;
  factors?: Array<{ name: string; score: number | null; available: boolean }>;
};

type Props = {
  initialItems: SignalTableItem[];
  initialNextCursor: string | null;
  pageSize: number;
  days: number;
  conviction: string;
  tier: string;
};

function buildSignalsApiUrl(
  days: number,
  conviction: string,
  tier: string,
  pageSize: number,
  cursor?: string | null,
): string {
  const params = new URLSearchParams();
  params.set("days", String(days));
  params.set("limit", String(pageSize));
  if (conviction) params.set("min_conviction", conviction);
  if (tier) params.set("tier", tier);
  if (cursor) params.set("cursor", cursor);
  return `/api/v1/earnings/signals?${params.toString()}`;
}

export function SignalsListSection({
  initialItems,
  initialNextCursor,
  pageSize,
  days,
  conviction,
  tier,
}: Props) {
  const [items, setItems] = useState(initialItems);
  const [nextCursor, setNextCursor] = useState(initialNextCursor);

  const onLoadMore = useCallback(async () => {
    if (!nextCursor) return;
    const res = await fetch(
      buildSignalsApiUrl(days, conviction, tier, pageSize, nextCursor),
    );
    if (!res.ok) throw new Error("fetch failed");
    const body = (await res.json()) as {
      items: SignalTableItem[];
      nextCursor: string | null;
    };
    setItems((prev) => [...prev, ...body.items]);
    setNextCursor(body.nextCursor);
  }, [conviction, days, nextCursor, pageSize, tier]);

  return (
    <div className="mt-6">
      <SignalsTable items={items} />
      <LoadMoreButton hasMore={Boolean(nextCursor)} onLoadMore={onLoadMore} />
    </div>
  );
}
