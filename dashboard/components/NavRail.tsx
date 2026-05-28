import Link from "next/link";

import { AuthNav } from "./AuthNav";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Left rail for laptop (>= lg) layout. Sticky to top of viewport so the masthead
 * and nav stay reachable as the main column scrolls. Hidden on mobile / tablet —
 * (app)/layout.tsx renders a compact horizontal masthead below lg.
 */
export function NavRail() {
  return (
    <aside className="hidden lg:sticky lg:top-10 lg:block lg:self-start lg:pr-4">
      <Link href="/" className="block pb-8">
        <span className="block font-serif text-[28px] font-semibold leading-none tracking-[-0.02em] text-ink">
          Tech Pulse
        </span>
        <span className="mt-2 block font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          科技脈搏
        </span>
      </Link>

      <nav
        aria-label="Primary"
        className="flex flex-col gap-3 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft"
      >
        <Link href="/" className="hover:text-accent">
          Today
        </Link>
        <Link href="/archive" className="hover:text-accent">
          Archive
        </Link>
        <Link href="/earnings" className="hover:text-accent">
          財報
        </Link>
        <Link href="/signals" className="hover:text-accent">
          訊號
        </Link>
        <Link href="/calibration" className="hover:text-accent">
          校驗
        </Link>
        <Link href="/macro" className="hover:text-accent">
          宏觀
        </Link>
        <Link href="/portfolio" className="hover:text-accent">
          持倉
        </Link>
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
    <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-3 pb-6 lg:hidden">
      <Link href="/" className="block">
        <span className="font-serif text-[28px] font-semibold tracking-[-0.02em] text-ink sm:text-[32px]">
          Tech Pulse
        </span>
        <span className="ml-3 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
          科技脈搏
        </span>
      </Link>
      <nav className="flex flex-wrap items-center gap-x-5 gap-y-2 font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft">
        <Link href="/" className="hover:text-accent">
          Today
        </Link>
        <Link href="/archive" className="hover:text-accent">
          Archive
        </Link>
        <Link href="/earnings" className="hover:text-accent">
          財報
        </Link>
        <Link href="/signals" className="hover:text-accent">
          訊號
        </Link>
        <Link href="/calibration" className="hover:text-accent">
          校驗
        </Link>
        <Link href="/macro" className="hover:text-accent">
          宏觀
        </Link>
        <Link href="/portfolio" className="hover:text-accent">
          持倉
        </Link>
        <AuthNav />
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="font-sans text-meta text-ink-faint">
            顯示模式
          </span>
          <ThemeToggle />
        </span>
      </nav>
    </header>
  );
}
