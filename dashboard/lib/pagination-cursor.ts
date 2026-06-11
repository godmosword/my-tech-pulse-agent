import { z } from "zod";

const ItemCursorSchema = z.object({
  d: z.string().min(1),
  i: z.string().min(1),
});

const EarningsCursorSchema = z.object({
  p: z.string().min(1),
  r: z.string().min(1),
});

const SignalCursorSchema = z.object({
  s: z.number(),
  r: z.string().min(1),
});

export interface ItemCursor {
  deliveredAtIso: string;
  id: string;
}

export interface EarningsCursor {
  publishedAtIso: string;
  reportId: string;
}

export interface SignalCursor {
  score: number;
  reportId: string;
}

function toBase64Url(value: string): string {
  return Buffer.from(value, "utf-8").toString("base64url");
}

function fromBase64Url(value: string): string | null {
  try {
    return Buffer.from(value, "base64url").toString("utf-8");
  } catch {
    return null;
  }
}

function encodePayload(payload: unknown): string {
  return toBase64Url(JSON.stringify(payload));
}

function decodePayload<T>(
  raw: string,
  schema: z.ZodType<T>,
): T | null {
  const decoded = fromBase64Url(raw.trim());
  if (!decoded) return null;
  let json: unknown;
  try {
    json = JSON.parse(decoded);
  } catch {
    return null;
  }
  const parsed = schema.safeParse(json);
  return parsed.success ? parsed.data : null;
}

export function encodeItemCursor(cursor: ItemCursor): string {
  return encodePayload({ d: cursor.deliveredAtIso, i: cursor.id });
}

export function decodeItemCursor(raw: string | null | undefined): ItemCursor | null {
  if (!raw?.trim()) return null;
  const parsed = decodePayload(raw, ItemCursorSchema);
  if (!parsed) return null;
  return { deliveredAtIso: parsed.d, id: parsed.i };
}

export function encodeEarningsCursor(cursor: EarningsCursor): string {
  return encodePayload({ p: cursor.publishedAtIso, r: cursor.reportId });
}

export function decodeEarningsCursor(
  raw: string | null | undefined,
): EarningsCursor | null {
  if (!raw?.trim()) return null;
  const parsed = decodePayload(raw, EarningsCursorSchema);
  if (!parsed) return null;
  return { publishedAtIso: parsed.p, reportId: parsed.r };
}

export function encodeSignalCursor(cursor: SignalCursor): string {
  return encodePayload({ s: cursor.score, r: cursor.reportId });
}

export function decodeSignalCursor(
  raw: string | null | undefined,
): SignalCursor | null {
  if (!raw?.trim()) return null;
  const parsed = decodePayload(raw, SignalCursorSchema);
  if (!parsed) return null;
  return { score: parsed.s, reportId: parsed.r };
}
