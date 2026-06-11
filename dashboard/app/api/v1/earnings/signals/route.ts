import { apiJson, withApiAuth } from "@/lib/api-route";
import { getPortfolioTierSets } from "@/lib/portfolio-server";
import {
  listSignalsLegacy,
  listSignalsPage,
} from "@/lib/signals-list-page";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const days = Math.min(90, Math.max(1, Number(url.searchParams.get("days") || 30)));
  const minConviction = url.searchParams.get("min_conviction") || undefined;
  const tierFilter = url.searchParams.get("tier") || undefined;
  const cursor = url.searchParams.get("cursor");
  const limitRaw = url.searchParams.get("limit");
  const limitParsed = limitRaw ? Number(limitRaw) : NaN;
  const limit =
    Number.isFinite(limitParsed) && limitParsed > 0
      ? Math.min(100, Math.max(1, Math.floor(limitParsed)))
      : undefined;

  const { holdingsSet, watchlistSet } = getPortfolioTierSets();
  const query = {
    days,
    minConviction,
    tierFilter,
    limit,
    cursor,
  };

  const isPaginated = limit != null || Boolean(cursor);
  const page = isPaginated
    ? await listSignalsPage(query, holdingsSet, watchlistSet)
    : await listSignalsLegacy(
        { days, minConviction, tierFilter },
        holdingsSet,
        watchlistSet,
      );

  const items = isPaginated
    ? page.items
    : page.items.map((item) => ({
        ticker: item.ticker,
        quarter_label: item.quarter_label,
        score: item.score,
        rating: item.rating,
        conviction: item.conviction,
        top_factor: item.top_factor,
        report_id: item.report_id,
        portfolio_tier: item.portfolio_tier,
      }));

  return apiJson({ items, count: items.length, days, nextCursor: page.nextCursor });
});
