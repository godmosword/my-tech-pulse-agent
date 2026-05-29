import { apiJson, withApiAuth } from "@/lib/api-route";
import {
  loadClustersSnapshot,
  loadCompanyRelationships,
  marketContextForTicker,
} from "@/lib/relationship-data";

export const GET = withApiAuth(async (request) => {
  const ticker = request.nextUrl.searchParams.get("ticker")?.trim().toUpperCase();
  if (!ticker || !/^[A-Z][A-Z0-9.\-]{0,9}$/.test(ticker)) {
    return apiJson(
      { error: "invalid_ticker", detail: "ticker query param required" },
      { status: 400 },
    );
  }

  const business = loadCompanyRelationships(ticker);
  const clusters = loadClustersSnapshot();
  const market = marketContextForTicker(ticker, clusters);

  return apiJson({
    business: business ?? {
      ticker,
      edges: [],
      source_form: "10-K",
    },
    market,
  });
});
