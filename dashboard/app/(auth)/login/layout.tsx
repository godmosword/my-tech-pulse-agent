import Link from "next/link";

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "讀者登入",
  description: "登入後可閱讀完整專欄中文全文與英文對照。",
};

/**
 * 獨立登入殼層：不含主站 Today／Archive 導覽，登入成功由 POST /api/auth/login 303 導向 returnTo。
 */
export default function LoginStandaloneLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-paper-tint">
      <div className="flex flex-1 flex-col items-center justify-center px-5 py-14 sm:py-20">
        <Link
          href="/"
          className="mb-10 text-center font-serif text-[22px] font-semibold tracking-[-0.02em] text-ink underline-offset-4 hover:text-accent hover:underline sm:text-[26px]"
        >
          Tech Pulse
          <span className="mt-1 block font-sans text-kicker font-semibold uppercase tracking-[0.14em] text-ink-soft">
            科技脈搏
          </span>
        </Link>
        <div className="w-full max-w-md border border-rule bg-paper px-6 py-10 shadow-sm sm:px-10 sm:py-12">
          {children}
        </div>
      </div>
      <p className="pb-8 text-center font-sans text-meta text-ink-faint">
        僅供授權讀者使用
      </p>
    </div>
  );
}
