import { apiJson, withApiAuth } from "@/lib/api-route";
import { loadUpcomingEarnings } from "@/lib/earnings-portal";
import { withPortfolioTierOnSymbols } from "@/lib/portfolio-server";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const days = Math.min(60, Math.max(1, Number(url.searchParams.get("days") || 14)));

  try {
    const payload = await loadUpcomingEarnings(days);
    const items = withPortfolioTierOnSymbols(payload.items);
    return apiJson({
      ...payload,
      items,
      available: true,
      source: "tech_pulse_earnings_api",
    });
  } catch (err) {
    console.error("[api/v1/earnings/upcoming]", err);
    return apiJson(
      {
        available: false,
        error: "earnings_upcoming_unavailable",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 503 },
    );
  }
});
