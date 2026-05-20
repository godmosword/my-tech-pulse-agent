import "server-only";

import { timingSafeEqual } from "crypto";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { isPublicReadMode } from "./env-public-read";
import { getReaderSession } from "./session";

export interface ApiAccess {
  /** 可回傳完整 summary_en / zh_body */
  full: boolean;
}

function readBearerToken(request: NextRequest): string {
  const header = request.headers.get("authorization") ?? "";
  const match = header.match(/^Bearer\s+(.+)$/i);
  return (match?.[1] ?? "").trim();
}

function tokensEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a, "utf8");
  const bb = Buffer.from(b, "utf8");
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

/**
 * /api/v1 授權：
 * - `API_READ_TOKEN` Bearer → 完整欄位
 * - 公開讀模式 + reader cookie → 完整欄位
 * - 公開讀模式 + 匿名 → 公開層（標題／繁中摘要）
 * - 非公開讀且未帶有效 Bearer → 401
 */
export async function authorizeApiRequest(
  request: NextRequest,
): Promise<{ ok: true; access: ApiAccess } | { ok: false; response: NextResponse }> {
  const configured = process.env.API_READ_TOKEN?.trim() ?? "";
  const provided = readBearerToken(request);

  if (configured && provided && tokensEqual(provided, configured)) {
    return { ok: true, access: { full: true } };
  }

  if (!isPublicReadMode()) {
    if (!configured) {
      return {
        ok: false,
        response: NextResponse.json(
          { error: "API_READ_TOKEN not configured" },
          { status: 503 },
        ),
      };
    }
    return {
      ok: false,
      response: NextResponse.json({ error: "unauthorized" }, { status: 401 }),
    };
  }

  const session = await getReaderSession();
  return { ok: true, access: { full: session !== null } };
}

export function apiJson(
  data: unknown,
  init?: { status?: number; headers?: Record<string, string> },
): NextResponse {
  return NextResponse.json(data, {
    status: init?.status ?? 200,
    headers: {
      "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300",
      ...init?.headers,
    },
  });
}
