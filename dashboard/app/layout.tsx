import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "科技脈搏 · Tech Pulse",
  description: "Daily tech intelligence digest — deep insights + curated headlines",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW">
      <body>
        <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 sm:py-10">
          <header className="mb-8 flex items-center justify-between border-b border-slate-200/60 pb-4 dark:border-slate-700/40">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              📡 <span className="ml-1">科技脈搏</span>
            </Link>
            <nav className="flex items-center gap-4 text-sm text-ink-muted">
              <Link href="/" className="hover:text-ink">
                最新
              </Link>
              <Link href="/archive" className="hover:text-ink">
                時間軸
              </Link>
            </nav>
          </header>
          <main>{children}</main>
          <footer className="mt-16 border-t border-slate-200/60 pt-4 text-xs text-ink-subtle dark:border-slate-700/40">
            視覺基準以 Telegram digest 為準 · Powered by Firestore
            {" "}
            <code className="font-mono">tech_pulse_memory_items</code>
          </footer>
        </div>
      </body>
    </html>
  );
}
