import "server-only";

import { cert, getApps, initializeApp, type App } from "firebase-admin/app";
import { getFirestore, type Firestore } from "firebase-admin/firestore";

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
    const credentials = JSON.parse(decoded);
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
    published_at_iso: toIsoString(item.published_at),
    delivered_at_iso: toIsoString(item.delivered_at),
    themes,
  };
}

export interface ListOptions {
  limit?: number;
  since?: Date;
}

export async function listLatestItems({
  limit = 60,
  since,
}: ListOptions = {}): Promise<RenderableItem[]> {
  let query = db().collection(COLLECTION).orderBy("delivered_at", "desc");
  if (since) query = query.where("delivered_at", ">=", since);
  const snap = await query.limit(limit).get();
  const items: RenderableItem[] = [];
  for (const doc of snap.docs) {
    const r = toRenderable(doc.id, doc.data());
    if (r) items.push(r);
  }
  return items;
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

export function digestCollectionName(): string {
  return DIGEST_COLLECTION;
}

/** Latest pipeline digest snapshot (`tech_pulse_digests`), if any. */
export async function getLatestDigestSnapshot(): Promise<Record<
  string,
  unknown
> | null> {
  const snap = await db()
    .collection(DIGEST_COLLECTION)
    .orderBy("delivered_at", "desc")
    .limit(1)
    .get();
  if (snap.empty) return null;
  const doc = snap.docs[0]!;
  return { ...(doc.data() as Record<string, unknown>), digest_id: doc.id };
}
