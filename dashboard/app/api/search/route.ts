import { NextResponse, type NextRequest } from "next/server";

import { searchPortal } from "@/lib/search-firestore";
import { SearchQuerySchema } from "@/lib/search-query";

/**
 * In-app search for the NavSearch chrome. Deliberately NOT under `/api/v1`:
 * the v1 endpoints require a Bearer token (or reader cookie) and 401 anonymous
 * browser requests in non-public-read mode, which the in-page search bar can't
 * satisfy. This route sits at the same trust level as the pages it lives on —
 * the Basic Auth middleware covers it in private deployments, and it is open in
 * public-read mode — and only ever returns non-sensitive titles / links.
 */
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const q = request.nextUrl.searchParams.get("q") ?? "";
  const parsed = SearchQuerySchema.safeParse({ q });
  if (!parsed.success) {
    const code = parsed.error.issues[0]?.message ?? "invalid_query";
    return NextResponse.json({ error: code }, { status: 400 });
  }

  try {
    const results = await searchPortal(parsed.data.q);
    return NextResponse.json(results, {
      headers: { "Cache-Control": "private, max-age=30" },
    });
  } catch (err) {
    console.error("[api/search]", err);
    return NextResponse.json({ error: "internal_error" }, { status: 500 });
  }
}
