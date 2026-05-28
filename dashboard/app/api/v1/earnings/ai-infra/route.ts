import { listEarningsReports } from "@/lib/earnings-firestore";
import { apiJson, authorizeApiRequest } from "@/lib/api-auth";
import { withPortfolioTierOnReports } from "@/lib/portfolio-server";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const auth = await authorizeApiRequest(request);
  if (!auth.ok) return auth.response;

  const signal = request.nextUrl.searchParams.get("signal")?.trim();
  const limit = Math.min(Number(request.nextUrl.searchParams.get("limit")) || 30, 80);

  let rows = await listEarningsReports({ limit: limit * 2, maxTier: 5 });
  if (signal) {
    rows = rows.filter((r) => r.ai_infra_signal === signal);
  } else {
    rows = rows.filter(
      (r) => r.ai_infra_signal && r.ai_infra_signal !== "not_relevant",
    );
  }
  return apiJson({ items: rows.slice(0, limit) });
}
