import Link from "next/link";

import { AuthNav } from "./AuthNav";
import { BrandMark } from "./BrandMark";
import { MobileMastheadTop } from "./MobileMastheadTop";
import { NavSearch } from "./NavSearch";
import { ThemeToggle } from "./ThemeToggle";

/** Reading surface — the editorial feed. */
const readingLinks = (
  <>
    <Link href="/" className="hover:text-accent">
      Today
    </Link>
    <Link href="/archive" className="hover:text-accent">
      Archive
    </Link>
  </>
);

/** Invest hub entry. Kept primary on every breakpoint. */
const investLink = (
  <Link href="/invest" className="hover:text-accent">
    投資 <span className="normal-case tracking-normal">Invest</span>
  </Link>
);

/**
 * Pages that live under the Invest hub. They are top-level routes, so the label
 * deliberately avoids implying a URL hierarchy ("投資相關頁", not "子頁").
 */
const investRelatedLinks: { href: string; label: string }[] = [
  { href: "/portfolio", label: "持倉" },
  { href: "/signals", label: "訊號" },
  { href: "/earnings", label: "財報" },
  { href: "/macro", label: "宏觀" },
  { href: "/calibration", label: "校驗" },
];

function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-faint">
      {children}
    </p>
  );
}

/**
 * Left rail for laptop (>= lg) layout. Sticky to top of viewport so the masthead
 * and nav stay reachable as the main column scrolls. Hidden on mobile / tablet —
 * (app)/layout.tsx renders a compact horizontal masthead below lg.
 *
 * Grouped into 閱讀 / 投資 / 系統 so the five Invest-related pages are
 * discoverable from the rail instead of only via in-page "more →" links.
 */
export function NavRail() {
  return (
    <aside className="hidden lg:sticky lg:top-10 lg:block lg:self-start lg:pr-4">
      <BrandMark variant="rail" className="pb-8 min-w-0" />
      <NavSearch variant="rail" />

      <nav
        aria-label="Primary"
        className="flex flex-col gap-6 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft"
      >
        <div className="flex flex-col gap-3">
          <GroupLabel>閱讀</GroupLabel>
          {readingLinks}
        </div>

        <div className="flex flex-col gap-3">
          <GroupLabel>投資</GroupLabel>
          {investLink}
          <ul className="flex flex-col gap-2 border-l border-rule pl-3 text-ink-faint">
            {investRelatedLinks.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="hover:text-accent">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex flex-col gap-3">
          <GroupLabel>系統</GroupLabel>
          <Link href="/health" className="hover:text-accent">
            營運摘要
          </Link>
          <AuthNav />
        </div>
      </nav>

      <div className="mt-10 border-t border-rule pt-6">
        <GroupLabel>顯示模式</GroupLabel>
        <div className="mt-3">
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}

/**
 * Mobile masthead — horizontal bar shown below lg. Keeps three primary entries
 * (Today / Archive / Invest) plus a quieter secondary row for the system link
 * and auth, so phones aren't stuck behind a wall of 7–8 links. The five
 * Invest-related pages are reached from inside the Invest hub on mobile.
 */
export function MobileMasthead() {
  return (
    <header className="space-y-3 pb-6 lg:hidden">
      <MobileMastheadTop />
      <nav
        aria-label="Primary"
        className="flex flex-wrap items-center gap-x-5 gap-y-2 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft"
      >
        {readingLinks}
        <span aria-hidden className="hidden h-3 w-px bg-rule sm:inline-block" />
        {investLink}
      </nav>
      <nav
        aria-label="Secondary"
        className="flex flex-wrap items-center gap-x-5 gap-y-2 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-faint"
      >
        <Link href="/health" className="hover:text-accent">
          營運摘要
        </Link>
        <span aria-hidden className="h-3 w-px bg-rule" />
        <AuthNav />
      </nav>
    </header>
  );
}
