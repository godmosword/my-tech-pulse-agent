/** Reader-facing dates — always Asia/Taipei. */
export const DASHBOARD_TIMEZONE = "Asia/Taipei";

const DAY_KEY_RE = /^\d{4}-\d{2}-\d{2}$/;

export function parseDashboardInstant(
  iso: string | null | undefined,
): Date | null {
  if (!iso?.trim()) return null;
  const raw = iso.trim();
  if (DAY_KEY_RE.test(raw)) {
    return new Date(`${raw}T12:00:00+08:00`);
  }
  const d = new Date(raw);
  return Number.isFinite(d.getTime()) ? d : null;
}

/** `yyyy-mm-dd` calendar key in Asia/Taipei (for day boundaries). */
export function dayKeyTaipei(instant: Date): string {
  return instant.toLocaleDateString("en-CA", { timeZone: DASHBOARD_TIMEZONE });
}

/** Date only — e.g. 2026年5月18日 */
export function formatDashboardDate(iso: string | null | undefined): string {
  const d = parseDashboardInstant(iso);
  if (!d) return "";
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: DASHBOARD_TIMEZONE,
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(d);
}

/** Date + time — e.g. 2026年5月18日 下午6:30 */
export function formatDashboardDateTime(iso: string | null | undefined): string {
  const d = parseDashboardInstant(iso);
  if (!d) return "";
  return new Intl.DateTimeFormat("zh-TW", {
    timeZone: DASHBOARD_TIMEZONE,
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(d);
}

/** Compact inline meta — e.g. 5月18日 · 18:30 */
export function formatDashboardMetaDateTime(
  iso: string | null | undefined,
): string {
  const d = parseDashboardInstant(iso);
  if (!d) return "";
  const date = new Intl.DateTimeFormat("zh-TW", {
    timeZone: DASHBOARD_TIMEZONE,
    month: "short",
    day: "numeric",
  }).format(d);
  const time = new Intl.DateTimeFormat("zh-TW", {
    timeZone: DASHBOARD_TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
  return `${date} · ${time}`;
}
