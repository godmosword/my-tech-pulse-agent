/** B 路線：標題／摘要公開、正文登入後可讀。 */
export function isPublicReadMode(): boolean {
  const v = process.env.DASHBOARD_PUBLIC_READ?.trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}
