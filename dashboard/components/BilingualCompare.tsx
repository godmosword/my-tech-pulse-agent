import { Kicker } from "./Kicker";

interface BilingualCompareProps {
  englishTitle: string | null;
  englishSummary: string | null;
  presentation: "details" | "stacked";
}

/**
 * title/summary ↔ zh_title/zh_summary 對照。不必等 zh_body。
 * details：InstantCard full；stacked：內文頁分欄。
 */
export function BilingualCompare({
  englishTitle,
  englishSummary,
  presentation,
}: BilingualCompareProps) {
  if (!englishTitle && !englishSummary) return null;

  if (presentation === "details") {
    return (
      <details className="font-sans text-meta text-ink-soft">
        <summary className="cursor-pointer text-accent underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
          中英對照
        </summary>
        {englishTitle && (
          <p className="mt-2 font-serif text-body text-ink">{englishTitle}</p>
        )}
        {englishSummary && (
          <p className="mt-2 whitespace-pre-line text-body text-ink-soft">
            {englishSummary}
          </p>
        )}
      </details>
    );
  }

  return (
    <>
      {englishTitle && (
        <div className="space-y-2">
          <Kicker>英文標題</Kicker>
          <p className="font-serif text-dek text-ink">{englishTitle}</p>
        </div>
      )}
      {englishSummary && (
        <div className={`space-y-2${englishTitle ? " border-t border-rule pt-6" : ""}`}>
          <Kicker>英文摘要</Kicker>
          <p className="whitespace-pre-line font-sans text-body leading-[1.65] text-ink-soft">
            {englishSummary}
          </p>
        </div>
      )}
    </>
  );
}
