import Link from "next/link";
import { redirect } from "next/navigation";

import { isPublicReadMode } from "@/lib/env-public-read";
import { getReaderSession } from "@/lib/session";

export const dynamic = "force-dynamic";

function safeReturnTo(v: string | null): string {
  const x = (v || "/").trim() || "/";
  if (!x.startsWith("/") || x.startsWith("//")) return "/";
  return x;
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ returnTo?: string; error?: string }>;
}) {
  if (!isPublicReadMode()) {
    redirect("/");
  }

  const session = await getReaderSession();
  const sp = await searchParams;
  const returnTo = safeReturnTo(sp.returnTo ?? null);
  if (session) {
    redirect(returnTo);
  }

  const err = sp.error === "1";

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="font-serif text-[28px] tracking-[-0.02em] text-ink">讀者登入</h1>
        <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-soft">
          登入後可閱讀完整專欄正文（與 Basic Auth 帳密相同）
        </p>
      </header>

      {err && (
        <p
          role="alert"
          className="rounded border border-rule bg-ink/[0.03] px-3 py-2 font-sans text-meta text-ink"
        >
          帳號或密碼不正確，請再試一次。
        </p>
      )}

      <form
        action="/api/auth/login"
        method="post"
        className="space-y-4 border-t border-rule pt-6"
      >
        <input type="hidden" name="returnTo" value={returnTo} />
        <div className="space-y-2">
          <label htmlFor="user" className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
            帳號
          </label>
          <input
            id="user"
            name="user"
            autoComplete="username"
            required
            className="w-full border border-rule bg-white px-3 py-2 font-sans text-body text-ink outline-none ring-accent focus:ring-1"
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="password" className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
            密碼
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="w-full border border-rule bg-white px-3 py-2 font-sans text-body text-ink outline-none ring-accent focus:ring-1"
          />
        </div>
        <button
          type="submit"
          className="w-full border border-ink bg-ink px-4 py-3 font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-paper hover:bg-ink/90"
        >
          登入
        </button>
      </form>

      <p className="font-sans text-meta text-ink-soft">
        <Link href={returnTo} className="text-accent underline-offset-4 hover:underline">
          返回上一頁
        </Link>
      </p>
    </div>
  );
}
