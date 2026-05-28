import { apiJson, withApiAuth } from "@/lib/api-route";
import { buildPortfolioPayload } from "@/lib/portfolio-server";

export const dynamic = "force-dynamic";

export const GET = withApiAuth(async () => {
  try {
    const payload = await buildPortfolioPayload();
    return apiJson(payload);
  } catch (err) {
    console.error("[api/v1/portfolio]", err);
    return apiJson(
      { error: "portfolio_unavailable", detail: err instanceof Error ? err.message : String(err) },
      { status: 503 },
    );
  }
});
