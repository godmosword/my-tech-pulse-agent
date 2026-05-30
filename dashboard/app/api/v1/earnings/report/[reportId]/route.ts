import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authorizeApiRequest, apiJson } from "@/lib/api-auth";
import { getEarningsReport } from "@/lib/earnings-firestore";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ reportId: string }> },
): Promise<NextResponse> {
  const auth = await authorizeApiRequest(request);
  if (!auth.ok) return auth.response;

  const { reportId } = await context.params;
  const row = await getEarningsReport(decodeURIComponent(reportId));
  if (!row) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  return apiJson({ item: row });
}
