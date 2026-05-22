import { apiJson, withApiAuth } from "@/lib/api-route";
import {
  loadNewsDigestItems,
  newsSourceLabel,
  themeCounts,
} from "@/lib/news-api";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const limit = Math.min(200, Math.max(1, Number(url.searchParams.get("limit") || 80)));

  try {
    const items = await loadNewsDigestItems(limit);
    return apiJson({
      themes: themeCounts(items),
      source: newsSourceLabel(),
      available: true,
    });
  } catch (err) {
    console.error("[api/v1/news/themes]", err);
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
