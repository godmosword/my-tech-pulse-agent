import { NextResponse } from "next/server";

import { isPublicReadMode } from "@/lib/env-public-read";
import {
  createReaderSessionToken,
  READER_SESSION_COOKIE,
  READER_SESSION_MAX_AGE,
  validateReaderLogin,
} from "@/lib/session";

function safeReturnTo(v: FormDataEntryValue | null): string {
  const x = String(v || "/").trim() || "/";
  if (!x.startsWith("/") || x.startsWith("//")) return "/";
  return x;
}

export async function POST(request: Request) {
  if (!isPublicReadMode()) {
    return NextResponse.json({ error: "Public read mode is disabled." }, { status: 404 });
  }

  const form = await request.formData();
  const user = String(form.get("user") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const returnTo = safeReturnTo(form.get("returnTo"));

  if (!validateReaderLogin(user, password)) {
    return NextResponse.redirect(
      new URL(`/login?error=1&returnTo=${encodeURIComponent(returnTo)}`, request.url),
      303
    );
  }

  const token = createReaderSessionToken(user);
  if (!token) {
    return NextResponse.json(
      { error: "Session signing is not configured (DASHBOARD_SESSION_SECRET)." },
      { status: 503 }
    );
  }

  const dest = new URL(returnTo, request.url);
  const res = NextResponse.redirect(dest, 303);
  res.cookies.set(READER_SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: READER_SESSION_MAX_AGE,
  });
  return res;
}
