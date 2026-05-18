import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import Link from "next/link";

import { AuthNav } from "@/components/AuthNav";
import { siteOrigin } from "@/lib/site-url";

import "./globals.css";

// Variable fonts loaded via next/font for zero CLS + automatic preloading.
// Inter handles body / UI; Source Serif 4 handles every headline and the
// three-part deep brief body. The CSS variables match tailwind.config.ts.
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "600"],
  variable: "--font-serif",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteOrigin()),
  title: {
    default: "Tech Pulse · 科技脈搏",
    template: "%s · Tech Pulse",
  },
  description:
    "Daily editorial digest of technology, capital and silicon — deep insights, curated headlines.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" className={`${inter.variable} ${sourceSerif.variable}`}>
      <body className="font-sans">
        <div className="mx-auto max-w-2xl px-5 pb-20 pt-8 sm:px-8 sm:pt-12">
          <header className="flex items-baseline justify-between gap-4 pb-6">
            <Link href="/" className="block">
              <span className="font-serif text-[26px] font-semibold tracking-[-0.02em] text-ink sm:text-[32px]">
                Tech Pulse
              </span>
              <span className="ml-3 font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
                科技脈搏
              </span>
            </Link>
            <nav className="flex items-center gap-5 font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
              <Link href="/" className="hover:text-accent">
                Today
              </Link>
              <Link href="/archive" className="hover:text-accent">
                Archive
              </Link>
              <AuthNav />
            </nav>
          </header>
          <div className="h-px w-full bg-ink" />
          <main className="mt-2">{children}</main>
          <footer className="mt-24 border-t border-rule pt-6 font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
            An editorial reading of the Tech Pulse pipeline · Powered by
            Firestore <code className="font-mono normal-case">tech_pulse_memory_items</code>
          </footer>
        </div>
      </body>
    </html>
  );
}
