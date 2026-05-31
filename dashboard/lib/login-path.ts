/** Reader login URL with safe post-auth redirect. */
export function loginReturnHref(returnToPath: string): string {
  return `/login?returnTo=${encodeURIComponent(returnToPath)}`;
}
