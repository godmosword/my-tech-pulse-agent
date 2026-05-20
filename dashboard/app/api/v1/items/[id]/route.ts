import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authorizeApiRequest, apiJson } from "@/lib/api-auth";
import { serializeItem } from "@/lib/api-serialize";
import { getItemById } from "@/lib/firestore";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const auth = await authorizeApiRequest(request);
  if (!auth.ok) return auth.response;

  const { id: rawId } = await context.params;
  const item = await getItemById(decodeURIComponent(rawId));
  if (!item) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  return apiJson({ item: serializeItem(item, auth.access) });
}
