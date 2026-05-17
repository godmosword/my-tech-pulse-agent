import { formatEditorialDate } from "@/lib/digest";
import { Hairline } from "./Hairline";
import { Kicker } from "./Kicker";

interface Props {
  latestDeliveredIso: string | null;
  totalShown: number;
  averageScore: number;
}

/**
 * Editorial issue masthead. The page-level brand sits in layout.tsx; this is
 * the date + issue meta that introduces today's digest.
 */
export function DigestHeader({
  latestDeliveredIso,
  totalShown,
  averageScore,
}: Props) {
  const dateLabel = formatEditorialDate(latestDeliveredIso);

  return (
    <section className="space-y-6 pb-8">
      <Kicker>{dateLabel ? `Today’s Pulse · ${dateLabel}` : "Today’s Pulse"}</Kicker>
      <h1 className="font-serif text-[34px] leading-[1.1] tracking-[-0.02em] text-ink sm:text-hero">
        The week in technology, capital and silicon.
      </h1>
      <p className="font-sans text-meta uppercase tracking-[0.08em] text-ink-faint">
        <span className="tabular-nums">{totalShown}</span> stories
        <span aria-hidden className="mx-2">·</span>
        Average score
        <span className="ml-2 font-mono tabular-nums text-ink-soft">
          {averageScore.toFixed(1)}
        </span>
      </p>
      <Hairline />
    </section>
  );
}
