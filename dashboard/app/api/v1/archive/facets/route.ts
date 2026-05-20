import { listLatestItems } from "@/lib/firestore";
import { buildFacets } from "@/lib/archive-filters";
import { apiJson, withApiAuth } from "@/lib/api-route";

const ARCHIVE_WINDOW_DAYS = 90;

export const GET = withApiAuth(async (request) => {
  const sp = request.nextUrl.searchParams;
  const daysRaw = parseInt(sp.get("window_days") ?? String(ARCHIVE_WINDOW_DAYS), 10);
  const windowDays = Number.isFinite(daysRaw) ? daysRaw : ARCHIVE_WINDOW_DAYS;
  const since = new Date(Date.now() - windowDays * 24 * 60 * 60 * 1000);

  const items = await listLatestItems({ limit: 400, since });
  const facets = buildFacets(items);

  return apiJson({
    window_days: windowDays,
    item_count: items.length,
    facets,
  });
});
