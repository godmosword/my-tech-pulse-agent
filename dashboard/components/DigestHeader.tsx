import { formatRelativeDate } from "@/lib/digest";

interface Props {
  latestDeliveredIso: string | null;
  totalShown: number;
  averageScore: number;
}

export function DigestHeader({
  latestDeliveredIso,
  totalShown,
  averageScore,
}: Props) {
  return (
    <section className="mb-8">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
        📡 科技脈搏
        {latestDeliveredIso && (
          <span className="ml-2 text-base font-normal text-ink-muted sm:text-lg">
            · {formatRelativeDate(latestDeliveredIso)}
          </span>
        )}
      </h1>
      <p className="mt-2 text-sm text-ink-muted">
        本期共 {totalShown} 則 · 平均分數{" "}
        <span className="font-mono">{averageScore.toFixed(1)}</span>
      </p>
    </section>
  );
}
