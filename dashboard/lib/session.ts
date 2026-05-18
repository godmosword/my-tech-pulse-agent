import "server-only";

import { createHmac, timingSafeEqual } from "crypto";
import { cookies } from "next/headers";

import { isPublicReadMode } from "./env-public-read";

const COOKIE = "tp_reader";
const MAX_AGE_SEC = 60 * 60 * 24 * 7;

function sessionSecret(): string | null {
  const s = process.env.DASHBOARD_SESSION_SECRET?.trim();
  return s || null;
}

function readerCredentials(): { user: string; pass: string } | null {
  const user = process.env.DASHBOARD_BASIC_AUTH_USER?.trim();
  const pass = process.env.DASHBOARD_BASIC_AUTH_PASS?.trim();
  if (!user || !pass) return null;
  return { user, pass };
}

function signPayload(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

export function createReaderSessionToken(username: string): string | null {
  const secret = sessionSecret();
  if (!secret) return null;
  const exp = Math.floor(Date.now() / 1000) + MAX_AGE_SEC;
  const body = JSON.stringify({ u: username, exp });
  const payload = Buffer.from(body, "utf8").toString("base64url");
  const sig = signPayload(payload, secret);
  return `${payload}.${sig}`;
}

export function verifyReaderSessionToken(token: string): string | null {
  const secret = sessionSecret();
  if (!secret) return null;
  const i = token.lastIndexOf(".");
  if (i <= 0) return null;
  const payload = token.slice(0, i);
  const sig = token.slice(i + 1);
  const expected = signPayload(payload, secret);
  try {
    const a = Buffer.from(sig);
    const b = Buffer.from(expected);
    if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  } catch {
    return null;
  }
  let parsed: { u?: string; exp?: number };
  try {
    parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
  } catch {
    return null;
  }
  if (!parsed.u || typeof parsed.exp !== "number") return null;
  if (parsed.exp < Math.floor(Date.now() / 1000)) return null;
  return parsed.u;
}

export async function getReaderSession(): Promise<string | null> {
  if (!isPublicReadMode()) return null;
  const secret = sessionSecret();
  if (!secret) return null;
  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE)?.value;
  if (!raw) return null;
  return verifyReaderSessionToken(raw);
}

export function validateReaderLogin(
  user: string,
  password: string
): boolean {
  const cred = readerCredentials();
  if (!cred) return false;
  return timingSafeStringEqual(user, cred.user) && timingSafeStringEqual(password, cred.pass);
}

function timingSafeStringEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a, "utf8");
  const bb = Buffer.from(b, "utf8");
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

export { COOKIE as READER_SESSION_COOKIE, MAX_AGE_SEC as READER_SESSION_MAX_AGE };
