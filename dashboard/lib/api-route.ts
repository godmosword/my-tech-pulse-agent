import "server-only";

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authorizeApiRequest, apiJson } from "./api-auth";

type ApiHandler = (
  request: NextRequest,
  ctx: { access: { full: boolean } },
) => Promise<NextResponse>;

/** Shared auth wrapper for /api/v1 handlers. */
export function withApiAuth(handler: ApiHandler) {
  return async function route(request: NextRequest): Promise<NextResponse> {
    const auth = await authorizeApiRequest(request);
    if (!auth.ok) return auth.response;
    try {
      return await handler(request, { access: auth.access });
    } catch (err) {
      console.error("[api/v1]", err);
      return NextResponse.json(
        { error: "internal_error" },
        { status: 500 },
      );
    }
  };
}

export { apiJson };
