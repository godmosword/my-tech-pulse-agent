import { NextResponse } from "next/server";

import { isPublicReadMode } from "@/lib/env-public-read";
import { READER_SESSION_COOKIE } from "@/lib/session";

export async function POST(request: Request) {
  if (!isPublicReadMode()) {
    return NextResponse.json({ error: "Public read mode is disabled." }, { status: 404 });
  }
  const res = NextResponse.redirect(new URL("/", request.url), 303);
  res.cookies.set(READER_SESSION_COOKIE, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return res;
}
