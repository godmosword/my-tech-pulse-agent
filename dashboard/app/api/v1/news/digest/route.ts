import { apiJson, withApiAuth } from "@/lib/api-route";
import {
  buildNewsExclusionSummary,
  loadNewsDigestItems,
  newsSourceLabel,
  themeCounts,
} from "@/lib/news-api";

export const GET = withApiAuth(async (request) => {
  const url = new URL(request.url);
  const date = url.searchParams.get("date");
  if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return apiJson(
      { error: "invalid_date", detail: "date must be YYYY-MM-DD" },
      { status: 422 },
    );
  }
  const limit = Math.min(50, Math.max(1, Number(url.searchParams.get("limit") || 20)));

  try {
    const items = await loadNewsDigestItems(limit, date);
    const themes = themeCounts(items);
    const summary = buildNewsExclusionSummary(items);
    return apiJson({
      date: date || null,
      limit,
      items,
      themes,
      /** For `tools/tech_pulse_tool.py` — JSON `summary` field. */
      summary,
      source: newsSourceLabel(),
      available: true,
    });
  } catch (err) {
    console.error("[api/v1/news/digest]", err);
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
