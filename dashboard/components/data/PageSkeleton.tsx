/**
 * Neutral loading placeholder for App Router `loading.tsx` boundaries.
 * Renders only the main content-column fallback (no app chrome). Decorative
 * blocks are aria-hidden; the container announces a busy status to AT.
 */
function Block({ className }: { className: string }) {
  return (
    <div
      aria-hidden="true"
      className={`motion-safe:animate-pulse rounded bg-paper-tint ${className}`}
    />
  );
}

export function PageSkeleton() {
  return (
    <div role="status" aria-busy="true" aria-label="載入中" className="space-y-8">
      <span className="sr-only">載入中…</span>

      {/* Heading area */}
      <div className="space-y-3">
        <Block className="h-3 w-24" />
        <Block className="h-8 w-2/3" />
        <Block className="h-4 w-full max-w-md" />
      </div>

      {/* Content rows */}
      <div className="space-y-3">
        <Block className="h-4 w-full" />
        <Block className="h-4 w-11/12" />
        <Block className="h-4 w-4/5" />
      </div>

      {/* Card blocks */}
      <div className="grid gap-4 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Block key={i} className="h-24 w-full" />
        ))}
      </div>
    </div>
  );
}
