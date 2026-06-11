import { apiJson, withApiAuth } from "@/lib/api-route";
import { searchPortal } from "@/lib/search-firestore";
import { SearchQuerySchema } from "@/lib/search-query";

export const GET = withApiAuth(async (request) => {
  const q = request.nextUrl.searchParams.get("q") ?? "";
  const parsed = SearchQuerySchema.safeParse({ q });
  if (!parsed.success) {
    const code = parsed.error.issues[0]?.message ?? "invalid_query";
    return apiJson({ error: code }, { status: 400 });
  }

  const results = await searchPortal(parsed.data.q);
  return apiJson(results);
});
