import { formatEditorialDate } from "@/lib/digest";
import { Hairline } from "./Hairline";
import { Kicker } from "./Kicker";

interface Props {
  latestDeliveredIso: string | null;
  totalShown: number;
  /** When true, content is from the latest batch, not today's Taipei window. */
  usingStaleFallback?: boolean;
}

/**
 * Editorial issue masthead. The page-level brand sits in layout.tsx; this is
 * the date + issue meta that introduces today's digest.
 */
export function DigestHeader({
  latestDeliveredIso,
  totalShown,
  usingStaleFallback = false,
}: Props) {
  const dateLabel = formatEditorialDate(latestDeliveredIso);
  const kicker = usingStaleFallback
    ? dateLabel
      ? `Latest Pulse · ${dateLabel}`
      : "Latest Pulse"
    : dateLabel
      ? `Today's Pulse · ${dateLabel}`
      : "Today's Pulse";

  return (
    <section className="space-y-6 pb-8">
      <Kicker>{kicker}</Kicker>
      {usingStaleFallback && (
        <p className="font-sans text-body text-ink-soft">
          今日 pipeline 尚未上線；以下為最近一次 delivery 的內容。
        </p>
      )}
      <h1 className="font-serif text-editorial-title text-ink sm:text-hero">
        The week in technology, capital and silicon.
      </h1>
      <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
        <span className="tabular-nums">{totalShown}</span> stories in this issue
      </p>
      <Hairline />
    </section>
  );
}
