import { listEarningsReports } from "@/lib/earnings-firestore";
import { apiJson, withApiAuth } from "@/lib/api-route";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const limit = Math.min(50, Math.max(1, Number(url.searchParams.get("limit") || 20)));
  const ticker = url.searchParams.get("ticker") || undefined;
  const maxTier = Number(url.searchParams.get("max_tier") || 5);

  const rows = await listEarningsReports({ limit, ticker, maxTier });
  return apiJson({ items: rows, count: rows.length });
});
