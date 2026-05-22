import { loadUpcomingEarnings } from "@/lib/earnings-portal";
import { apiJson, withApiAuth } from "@/lib/api-route";

/** Legacy alias: `horizon` ≈ `days` on `/earnings/upcoming`. */
export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const horizon = Math.min(90, Math.max(1, Number(url.searchParams.get("horizon") || 30)));
  const upcoming = await loadUpcomingEarnings(horizon);
  const events = upcoming.items.map((item) => ({
    ticker: item.symbol,
    company: item.symbol,
    tier: item.tier,
    event_date_iso: item.next_earnings_date,
    pillar: item.pillar,
    note: item.source,
  }));
  return apiJson({
    horizon_days: horizon,
    events,
    count: events.length,
    calendar_source: upcoming.calendar_source,
    as_of: upcoming.as_of,
  });
});
