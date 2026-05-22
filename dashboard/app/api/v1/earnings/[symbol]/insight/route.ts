import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

import { authorizeApiRequest, apiJson } from "@/lib/api-auth";
import { loadEarningsInsight } from "@/lib/earnings-portal";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ symbol: string }> },
): Promise<NextResponse> {
  const auth = await authorizeApiRequest(request);
  if (!auth.ok) return auth.response;

  const { symbol } = await context.params;
  const decoded = decodeURIComponent(symbol);
  try {
    const insight = await loadEarningsInsight(decoded);
    if (insight.reason === "invalid_symbol") {
      return apiJson({ error: "invalid_symbol", detail: "invalid symbol" }, { status: 400 });
    }
    return apiJson(insight);
  } catch (err) {
    console.error("[api/v1/earnings/[symbol]/insight]", err);
    return apiJson(
      {
        enabled: false,
        symbol: symbol.toUpperCase(),
        error: "earnings_insight_unavailable",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 503 },
    );
  }
}
