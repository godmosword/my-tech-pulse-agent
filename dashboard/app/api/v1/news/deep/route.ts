import { apiJson, withApiAuth } from "@/lib/api-route";
import {
  loadNewsDeepItems,
  newsSourceLabel,
  normalizePillar,
} from "@/lib/news-api";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const pillarRaw = url.searchParams.get("pillar");
  const canonical = normalizePillar(pillarRaw);
  if (pillarRaw && !canonical) {
    return apiJson(
      {
        error: "invalid_pillar",
        detail: "pillar must be one of ai, semiconductor, crypto",
      },
      { status: 422 },
    );
  }
  const limit = Math.min(50, Math.max(1, Number(url.searchParams.get("limit") || 20)));

  try {
    const items = await loadNewsDeepItems(limit, canonical || null);
    return apiJson({
      pillar: canonical || null,
      limit,
      items,
      source: newsSourceLabel(),
      available: true,
    });
  } catch (err) {
    console.error("[api/v1/news/deep]", err);
    return apiJson(
      {
        available: false,
        error: "news_firestore_unavailable",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 503 },
    );
  }
});
