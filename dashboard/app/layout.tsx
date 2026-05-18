import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";

import { siteOrigin } from "@/lib/site-url";

import "./globals.css";

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

// Runs synchronously in <head> before the first paint so the manual theme
// choice is applied without a flash. `data-theme="light|dark"` forces the
// palette in globals.css; absence falls back to prefers-color-scheme.
const themeBootstrap = `
try {
  var v = localStorage.getItem("tech-pulse-theme");
  if (v === "light" || v === "dark") {
    document.documentElement.setAttribute("data-theme", v);
  }
} catch (_) {}
`.trim();

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" className={`${inter.variable} ${sourceSerif.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body className="font-sans">{children}</body>
    </html>
  );
}
