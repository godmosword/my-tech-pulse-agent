import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

import { authorizeApiRequest, apiJson } from "@/lib/api-auth";
import { getNewsDeepById } from "@/lib/news-api";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ itemId: string }> },
): Promise<NextResponse> {
  const auth = await authorizeApiRequest(request);
  if (!auth.ok) return auth.response;

  const { itemId } = await context.params;
  try {
    const item = await getNewsDeepById(decodeURIComponent(itemId));
    if (!item) {
      return apiJson({ error: "not_found", detail: "news item not found" }, { status: 404 });
    }
    return apiJson(item);
  } catch (err) {
    console.error("[api/v1/news/deep/[itemId]]", err);
    return apiJson(
      {
        error: "news_firestore_unavailable",
        detail: err instanceof Error ? err.message : String(err),
      },
      { status: 503 },
    );
  }
}
