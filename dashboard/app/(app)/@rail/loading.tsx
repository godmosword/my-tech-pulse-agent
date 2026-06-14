/**
 * Minimal fallback for the right @rail parallel slot during data loading.
 * Decorative; the main content column's loading.tsx carries the busy status.
 */
export default function RailLoading() {
  return (
    <div aria-hidden="true" className="space-y-3">
      <div className="motion-safe:animate-pulse h-3 w-20 rounded bg-paper-tint" />
      <div className="motion-safe:animate-pulse h-20 w-full rounded bg-paper-tint" />
      <div className="motion-safe:animate-pulse h-16 w-full rounded bg-paper-tint" />
    </div>
  );
}
