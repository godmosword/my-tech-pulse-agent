import "server-only";

/** metadataBase、sitemap、robots 用；部署時請設為公開 HTTPS origin（無結尾斜線）。 */
export function siteOrigin(): string {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL?.trim() ||
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "") ||
    "http://localhost:3000";
  return raw.replace(/\/+$/, "");
}
