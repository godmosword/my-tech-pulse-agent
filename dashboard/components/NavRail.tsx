import Link from "next/link";

import { AuthNav } from "./AuthNav";
import { BrandMark } from "./BrandMark";
import { ThemeToggle } from "./ThemeToggle";

const readingLinks = (
  <>
    <Link href="/" className="hover:text-accent">
      Today
    </Link>
    <Link href="/archive" className="hover:text-accent">
      Archive
    </Link>
    <Link href="/health" className="hover:text-accent">
      營運摘要
    </Link>
  </>
);

const investLink = (
  <Link href="/invest" className="hover:text-accent">
    投資 <span className="normal-case tracking-normal">Invest</span>
  </Link>
);

/**
 * Left rail for laptop (>= lg) layout. Sticky to top of viewport so the masthead
 * and nav stay reachable as the main column scrolls. Hidden on mobile / tablet —
 * (app)/layout.tsx renders a compact horizontal masthead below lg.
 */
export function NavRail() {
  return (
    <aside className="hidden lg:sticky lg:top-10 lg:block lg:self-start lg:pr-4">
      <BrandMark variant="rail" className="pb-8 min-w-0" />

      <nav
        aria-label="Primary"
        className="flex flex-col gap-3 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft"
      >
        {readingLinks}
        <div className="my-1 border-t border-rule" aria-hidden />
        {investLink}
        <AuthNav />
      </nav>

      <div className="mt-10 border-t border-rule pt-6">
        <p className="mb-3 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-faint">
          顯示模式
        </p>
        <ThemeToggle />
      </div>
    </aside>
  );
}

/**
 * Mobile masthead — horizontal bar shown below lg. Keeps the brand visible and
 * surfaces the same nav links so phone / tablet users aren't stuck.
 */
export function MobileMasthead() {
  return (
    <header className="space-y-4 pb-6 lg:hidden">
      <div className="flex items-start justify-between gap-3">
        <BrandMark variant="mobile" className="min-w-0" />
        <div className="flex shrink-0 items-center gap-2 pt-1">
          <span className="sr-only">顯示模式</span>
          <ThemeToggle />
        </div>
      </div>
      <nav
        aria-label="Primary"
        className="flex flex-wrap items-center gap-x-5 gap-y-2 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft"
      >
        {readingLinks}
        <span aria-hidden className="hidden h-3 w-px bg-rule sm:inline-block" />
        {investLink}
        <AuthNav />
      </nav>
    </header>
  );
}
