import { listEarningsSince } from "@/lib/earnings-firestore";
import { apiJson, withApiAuth } from "@/lib/api-route";
import { withPortfolioTierOnReports } from "@/lib/portfolio-server";

const CONVICTION_RANK: Record<string, number> = {
  low: 0,
  medium: 1,
  high: 2,
};

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const days = Math.min(90, Math.max(1, Number(url.searchParams.get("days") || 30)));
  const minConviction = url.searchParams.get("min_conviction") || undefined;
  const tierFilter = url.searchParams.get("tier") || undefined;

  const since = new Date();
  since.setUTCDate(since.getUTCDate() - days);

  const rows = await listEarningsSince(since, { limit: 120, maxTier: 5 });
  const base = rows
    .filter((r) => r.investment_signal?.score != null)
    .map((r) => {
      const sig = r.investment_signal!;
      const top = [...(sig.factors || [])]
        .filter((f) => f.available && f.score != null)
        .sort((a, b) => (b.weight || 0) - (a.weight || 0))[0];
      return {
        ticker: r.ticker,
        quarter_label: r.quarter_label,
        score: sig.score,
        rating: sig.rating,
        conviction: sig.conviction,
        top_factor: top?.name ?? null,
        report_id: r.report_id,
      };
    });

  let items = withPortfolioTierOnReports(base);

  if (minConviction === "medium") {
    items = items.filter((i) => (CONVICTION_RANK[i.conviction] ?? 0) >= 1);
  } else if (minConviction === "high") {
    items = items.filter((i) => i.conviction === "high");
  }

  if (tierFilter === "holding") {
    items = items.filter((i) => i.portfolio_tier === "holding");
  } else if (tierFilter === "watchlist") {
    items = items.filter((i) => i.portfolio_tier === "watchlist");
  }

  items.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

  return apiJson({ items, count: items.length, days });
});
