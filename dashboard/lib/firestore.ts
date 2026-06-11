import "server-only";

import { cert, getApps, initializeApp, type App } from "firebase-admin/app";
import {
  FieldPath,
  getFirestore,
  type Firestore,
} from "firebase-admin/firestore";

import {
  MemoryItemSchema,
  toIsoString,
  type RenderableItem,
} from "./types";

const COLLECTION_PREFIX =
  process.env.FIRESTORE_COLLECTION_PREFIX?.trim() || "tech_pulse";
const COLLECTION =
  process.env.TECH_PULSE_FIRESTORE_COLLECTION?.trim() ||
  `${COLLECTION_PREFIX}_memory_items`;
const DIGEST_COLLECTION = `${COLLECTION_PREFIX}_digests`;

let cachedApp: App | null = null;

export function getApp(): App {
  if (cachedApp) return cachedApp;
  const existing = getApps();
  if (existing.length) {
    cachedApp = existing[0]!;
    return cachedApp;
  }

  const raw = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (raw) {
    const decoded = raw.trim().startsWith("{")
      ? raw
      : Buffer.from(raw, "base64").toString("utf-8");
    let credentials: Record<string, unknown>;
    try {
      credentials = JSON.parse(decoded) as Record<string, unknown>;
    } catch {
      throw new Error("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON");
    }
    cachedApp = initializeApp({ credential: cert(credentials) });
  } else {
    // Falls back to Application Default Credentials — works locally with
    // `gcloud auth application-default login` and on GCP runtimes.
    cachedApp = initializeApp();
  }
  return cachedApp;
}

function db(): Firestore {
  return getFirestore(getApp());
}

function toRenderable(id: string, raw: unknown): RenderableItem | null {
  const parsed = MemoryItemSchema.safeParse({ ...(raw as object), id });
  if (!parsed.success) return null;
  const item = parsed.data;
  const themes = item.category ? [item.category] : [];
  return {
    id: item.id,
    title: item.title,
    zh_title: item.zh_title ?? "",
    summary: item.summary,
    zh_summary: item.zh_summary ?? "",
    zh_body: item.zh_body ?? "",
    source_url: item.source_url,
    source_name: item.source_name,
    entity: item.entity,
    category: item.category,
    kind: item.kind,
    score: item.score,
    score_status: item.score_status,
    hook: item.hook ?? "",
    tickers: item.tickers ?? [],
    what_happened: item.what_happened ?? "",
    why_it_matters: item.why_it_matters ?? "",
    takeaway: item.takeaway?.takeaway_zh
      ? {
          item_id: item.takeaway.item_id ?? item.id,
          takeaway_zh: item.takeaway.takeaway_zh ?? "",
          angle: item.takeaway.angle ?? "其他",
          tickers: item.takeaway.tickers ?? [],
          confidence: item.takeaway.confidence ?? "medium",
        }
      : null,
    published_at_iso: toIsoString(item.published_at),
    delivered_at_iso: toIsoString(item.delivered_at),
    themes,
  };
}

export interface ListOptions {
  limit?: number;
  since?: Date;
}

export interface ItemFirestoreCursor {
  deliveredAtIso: string;
  id: string;
}

function deliveredAtFromIso(iso: string): Date {
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) {
    throw new Error(`invalid delivered_at cursor: ${iso}`);
  }
  return new Date(ms);
}

function baseItemsQuery(since?: Date) {
  let query = db()
    .collection(COLLECTION)
    .orderBy("delivered_at", "desc")
    .orderBy(FieldPath.documentId(), "desc");
  if (since) query = query.where("delivered_at", ">=", since);
  return query;
}

export async function listLatestItems({
  limit = 60,
  since,
}: ListOptions = {}): Promise<RenderableItem[]> {
  const snap = await baseItemsQuery(since).limit(limit).get();
  const items: RenderableItem[] = [];
  for (const doc of snap.docs) {
    const r = toRenderable(doc.id, doc.data());
    if (r) items.push(r);
  }
  return items;
}

export async function listLatestItemsAfter({
  limit,
  since,
  cursor,
}: {
  limit: number;
  since?: Date;
  cursor?: ItemFirestoreCursor;
}): Promise<{
  items: RenderableItem[];
  hasMore: boolean;
  lastCursor: ItemFirestoreCursor | null;
}> {
  let query = baseItemsQuery(since);
  if (cursor) {
    query = query.startAfter(
      deliveredAtFromIso(cursor.deliveredAtIso),
      cursor.id,
    );
  }
  const snap = await query.limit(limit + 1).get();
  const docs = snap.docs.slice(0, limit);
  const items: RenderableItem[] = [];
  for (const doc of docs) {
    const r = toRenderable(doc.id, doc.data());
    if (r) items.push(r);
  }
  const last = items.at(-1);
  return {
    items,
    hasMore: snap.docs.length > limit,
    lastCursor:
      last && last.delivered_at_iso
        ? { deliveredAtIso: last.delivered_at_iso, id: last.id }
        : null,
  };
}

export async function getItemById(
  id: string
): Promise<RenderableItem | null> {
  const doc = await db().collection(COLLECTION).doc(id).get();
  if (!doc.exists) return null;
  return toRenderable(doc.id, doc.data());
}

export function collectionName(): string {
  return COLLECTION;
}

/** All digest snapshots since a boundary (ascending — oldest run first). */
export async function listDigestSnapshotsSince(
  since: Date,
  { limit = 24 }: { limit?: number } = {},
): Promise<Record<string, unknown>[]> {
  const snap = await db()
    .collection(DIGEST_COLLECTION)
    .where("delivered_at", ">=", since)
    .orderBy("delivered_at", "asc")
    .limit(limit)
    .get();
  return snap.docs.map((doc) => ({
    ...(doc.data() as Record<string, unknown>),
    digest_id: doc.id,
  }));
}
