import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_TC, Noto_Serif_TC, Source_Serif_4 } from "next/font/google";

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

// CJK glyphs — Inter/Source Serif only ship Latin subsets, so Chinese text
// falls back to whatever system font is available. Loading Noto TC ensures
// 繁體中文 renders correctly on any device (Vercel preview, mobile, etc.).
const notoSansTc = Noto_Sans_TC({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-sans-cjk",
});

const notoSerifTc = Noto_Serif_TC({
  subsets: ["latin"],
  weight: ["400", "600"],
  display: "swap",
  variable: "--font-serif-cjk",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteOrigin()),
  title: {
    default: "Tech Pulse · 科技脈搏",
    template: "%s · Tech Pulse",
  },
  description:
    "Daily editorial digest of technology, capital and silicon — deep insights, curated headlines.",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "科技脈搏",
  },
  icons: {
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf7f2" },
    { media: "(prefers-color-scheme: dark)", color: "#16120e" },
  ],
};

// Runs synchronously in <head> before the first paint so the manual theme
// choice is applied without a flash. `data-theme="light|dark"` forces the
// palette in globals.css; absence falls back to prefers-color-scheme.
// The `js` class gates reveal-on-scroll animations: without JS the class is
// absent, so `.reveal` content stays fully visible (no hidden-by-default trap).
const themeBootstrap = `
document.documentElement.classList.add("js");
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
    <html
      lang="zh-TW"
      className={`${inter.variable} ${sourceSerif.variable} ${notoSansTc.variable} ${notoSerifTc.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body className="font-sans">{children}</body>
    </html>
  );
}
