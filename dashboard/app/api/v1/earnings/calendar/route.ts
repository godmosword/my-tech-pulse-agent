import { listEarningsCalendar } from "@/lib/earnings-firestore";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const horizon = Math.min(90, Math.max(1, Number(url.searchParams.get("horizon") || 30)));
  const events = await listEarningsCalendar(horizon);
  return apiJson({ horizon_days: horizon, events, count: events.length });
});
