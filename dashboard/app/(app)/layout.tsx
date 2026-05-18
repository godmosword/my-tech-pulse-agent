import { MobileMasthead, NavRail } from "@/components/NavRail";

/**
 * App chrome. Two layouts in one:
 *
 * - Below lg (1024px): single column with the horizontal masthead.
 * - lg+ : three-column editorial grid — NavRail / content / @rail slot.
 *
 * The right column is a parallel route slot. Each route can opt in by adding
 * an `@rail/page.tsx`; otherwise `@rail/default.tsx` renders. Pages that don't
 * want a right rail just have an empty default.
 */
export default function AppChromeLayout({
  children,
  rail,
}: {
  children: React.ReactNode;
  rail: React.ReactNode;
}) {
  return (
    <div className="mx-auto max-w-6xl px-5 pb-20 pt-8 sm:px-8 sm:pt-12 lg:px-12">
      <MobileMasthead />
      <div className="h-px w-full bg-ink lg:hidden" />

      <div className="mt-2 lg:mt-0 lg:grid lg:grid-cols-[180px_minmax(0,720px)_minmax(180px,240px)] lg:gap-12">
        <NavRail />

        <main className="min-w-0">{children}</main>

        <aside className="mt-16 border-t border-rule pt-8 lg:mt-0 lg:border-t-0 lg:pt-0 lg:sticky lg:top-10 lg:self-start">
          {rail}
        </aside>
      </div>

      <footer className="mt-24 border-t border-rule pt-6 font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
        An editorial reading of the Tech Pulse pipeline · Powered by Firestore{" "}
        <code className="font-mono normal-case">tech_pulse_memory_items</code>
      </footer>
    </div>
  );
}
