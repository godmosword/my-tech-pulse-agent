import "server-only";

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { cache } from "react";

function dataDir(): string {
  return join(process.cwd(), "data");
}

function readJsonFile(path: string): unknown {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

export const loadMemoryItemsRaw = cache((): Record<string, unknown>[] => {
  const parsed = readJsonFile(join(dataDir(), "memory_items.json"));
  if (!Array.isArray(parsed)) return [];
  return parsed.filter((row): row is Record<string, unknown> => !!row && typeof row === "object");
});

export const loadDigestSnapshotsRaw = cache((): Record<string, unknown>[] => {
  const parsed = readJsonFile(join(dataDir(), "digests.json"));
  if (!Array.isArray(parsed)) return [];
  return parsed.filter((row): row is Record<string, unknown> => !!row && typeof row === "object");
});

export const loadEarningsIndexRaw = cache((): Record<string, unknown>[] => {
  const parsed = readJsonFile(join(dataDir(), "earnings", "index.json"));
  if (!Array.isArray(parsed)) return [];
  return parsed.filter((row): row is Record<string, unknown> => !!row && typeof row === "object");
});

export function loadEarningsReportRaw(
  reportId: string,
): Record<string, unknown> | null {
  const safe = reportId.replaceAll("/", "_").replaceAll("..", "_");
  const parsed = readJsonFile(join(dataDir(), "earnings", `${safe}.json`));
  if (!parsed || typeof parsed !== "object") return null;
  return parsed as Record<string, unknown>;
}

export function itemIdOf(row: Record<string, unknown>): string {
  return String(row.item_id || row.id || "");
}

export function deliveredMs(row: Record<string, unknown>): number {
  const raw = row.delivered_at;
  if (typeof raw !== "string") return 0;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : 0;
}

export function publishedMs(row: Record<string, unknown>): number {
  const raw = row.published_at;
  if (typeof raw !== "string") return 0;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : 0;
}
