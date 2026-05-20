import { listLatestItems } from "@/lib/firestore";
import { aggregateTickers, startOfTodayTaipeiUtc } from "@/lib/api-query";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async (request) => {
  const sp = request.nextUrl.searchParams;
  const scope = sp.get("scope")?.trim() || "today";
  const limitRaw = parseInt(sp.get("limit") ?? "5", 10);
  const limit = Number.isFinite(limitRaw)
    ? Math.min(Math.max(1, limitRaw), 20)
    : 5;

  let since: Date | undefined;
  if (scope === "today") {
    since = startOfTodayTaipeiUtc();
  } else if (scope === "archive") {
    const days = parseInt(sp.get("window_days") ?? "90", 10);
    const windowDays = Number.isFinite(days) ? days : 90;
    since = new Date(Date.now() - windowDays * 24 * 60 * 60 * 1000);
  }

  let items = await listLatestItems({ limit: 80, since });
  if (scope === "today" && items.length === 0) {
    items = await listLatestItems({ limit: 80 });
  }

  const tickers = aggregateTickers(items, limit);
  return apiJson({
    scope,
    tickers,
    article_count: items.length,
  });
});
