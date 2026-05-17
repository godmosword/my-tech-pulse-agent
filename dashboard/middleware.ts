import { NextRequest, NextResponse } from "next/server";

/**
 * Basic Auth gate via env vars. Runs on Edge, so we use `atob` rather than
 * Node's Buffer.
 *
 * Skipped entirely when DASHBOARD_BASIC_AUTH_USER is unset — useful for local
 * dev or Vercel preview deploys behind their own auth.
 */
export function middleware(request: NextRequest): NextResponse {
  const user = process.env.DASHBOARD_BASIC_AUTH_USER;
  const pass = process.env.DASHBOARD_BASIC_AUTH_PASS;
  if (!user || !pass) return NextResponse.next();

  const header = request.headers.get("authorization") ?? "";
  if (header.startsWith("Basic ")) {
    try {
      const decoded = atob(header.slice(6));
      const sep = decoded.indexOf(":");
      if (sep !== -1) {
        const u = decoded.slice(0, sep);
        const p = decoded.slice(sep + 1);
        if (timingSafeEqual(u, user) && timingSafeEqual(p, pass)) {
          return NextResponse.next();
        }
      }
    } catch {
      // fall through to challenge
    }
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="科技脈搏 Dashboard", charset="UTF-8"',
    },
  });
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

export const config = {
  // Run on every page except Next.js internals AND `/api/revalidate`, which
  // is the pipeline webhook — that endpoint has its own token check and must
  // be reachable without Basic Auth credentials.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/revalidate).*)"],
};
