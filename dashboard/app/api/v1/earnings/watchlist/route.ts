import { apiJson, withApiAuth } from "@/lib/api-route";
import { watchlistEntries } from "@/lib/earnings-portal";

export const GET = withApiAuth(async () => {
  const entries = watchlistEntries();
  return apiJson({
    count: entries.length,
    entries,
    source: "config/earnings_watchlist.yaml",
    available: true,
  });
});
