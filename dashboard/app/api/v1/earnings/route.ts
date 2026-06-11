import { listEarningsReports, listEarningsReportsPage } from "@/lib/earnings-firestore";
import { apiJson, withApiAuth } from "@/lib/api-route";
import {
  decodeEarningsCursor,
  encodeEarningsCursor,
} from "@/lib/pagination-cursor";
import { withPortfolioTierOnReports } from "@/lib/portfolio-server";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const limit = Math.min(50, Math.max(1, Number(url.searchParams.get("limit") || 20)));
  const ticker = url.searchParams.get("ticker") || undefined;
  const maxTier = Number(url.searchParams.get("max_tier") || 5);
  const cursorRaw = url.searchParams.get("cursor");

  let items;
  let nextCursor: string | null = null;

  if (cursorRaw) {
    const decoded = decodeEarningsCursor(cursorRaw);
    if (!decoded) {
      return apiJson({ items: [], count: 0, nextCursor: null });
    }
    const page = await listEarningsReportsPage({
      limit,
      ticker,
      maxTier,
      cursor: {
        publishedAtIso: decoded.publishedAtIso,
        reportId: decoded.reportId,
      },
    });
    items = withPortfolioTierOnReports(page.items);
    nextCursor =
      page.hasMore && page.lastCursor
        ? encodeEarningsCursor({
            publishedAtIso: page.lastCursor.publishedAtIso,
            reportId: page.lastCursor.reportId,
          })
        : null;
  } else {
    const rows = await listEarningsReports({ limit, ticker, maxTier });
    items = withPortfolioTierOnReports(rows);
    const last = rows.at(-1);
    nextCursor =
      last && rows.length === limit && last.published_at_iso
        ? encodeEarningsCursor({
            publishedAtIso: last.published_at_iso,
            reportId: last.report_id,
          })
        : null;
  }

  return apiJson({ items, count: items.length, nextCursor });
});
