import Link from "next/link";

import { isPublicReadMode } from "@/lib/env-public-read";
import { getReaderSession } from "@/lib/session";

export async function AuthNav() {
  if (!isPublicReadMode()) return null;

  const user = await getReaderSession();

  if (user) {
    return (
      <div className="flex items-center gap-3 font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
        <span className="hidden sm:inline normal-case tracking-normal text-meta text-ink-faint">
          {user}
        </span>
        <form action="/api/auth/logout" method="post" className="inline">
          <button
            type="submit"
            className="hover:text-accent"
          >
            登出
          </button>
        </form>
      </div>
    );
  }

  return (
    <Link
      href="/login"
      className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft hover:text-accent"
    >
      登入
    </Link>
  );
}
