import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/revalidate?path=/  → forces ISR to rebuild the given route.
 *
 * Pipeline hits this right after `main.py` finishes archiving so the dashboard
 * picks up the latest digest without waiting for the 5-minute ISR window.
 *
 * Auth: `x-revalidate-token` header must match REVALIDATE_TOKEN env. We keep
 * this separate from the Basic Auth gate because the pipeline isn't a browser.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const token = process.env.REVALIDATE_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "REVALIDATE_TOKEN not configured" },
      { status: 503 }
    );
  }

  const provided = request.headers.get("x-revalidate-token") ?? "";
  if (provided !== token) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const path = request.nextUrl.searchParams.get("path") || "/";
  revalidatePath(path);

  // Always refresh the archive listing too — most pipeline runs deliver new
  // items that should surface there.
  if (path !== "/archive") revalidatePath("/archive");

  return NextResponse.json({ revalidated: true, path });
}
