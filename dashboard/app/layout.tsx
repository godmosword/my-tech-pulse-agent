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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" className={`${inter.variable} ${sourceSerif.variable}`}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
