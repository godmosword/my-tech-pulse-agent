import { NextResponse } from "next/server";

import { listEarningsReports } from "@/lib/earnings-firestore";
import { requireApiReadToken } from "@/lib/api-route";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = requireApiReadToken(request);
  if (!auth.ok) return auth.response;

  const url = new URL(request.url);
  const limit = Math.min(50, Math.max(1, Number(url.searchParams.get("limit") || 20)));
  const ticker = url.searchParams.get("ticker") || undefined;
  const maxTier = Number(url.searchParams.get("max_tier") || 5);

  const rows = await listEarningsReports({ limit, ticker, maxTier });
  return NextResponse.json({ items: rows, count: rows.length });
}
