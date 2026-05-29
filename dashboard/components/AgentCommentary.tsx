import { Kicker } from "./Kicker";

interface AgentCommentaryProps {
  whatHappened?: string | null;
  whyItMatters?: string | null;
  authenticated: boolean;
}

/**
 * Editorial agent take (what_happened / why_it_matters) on article detail pages.
 */
export function AgentCommentary({
  whatHappened,
  whyItMatters,
  authenticated,
}: AgentCommentaryProps) {
  const wh = whatHappened?.trim() ?? "";
  const why = whyItMatters?.trim() ?? "";
  const hasContent = Boolean(wh) || Boolean(why);

  if (!authenticated) {
    return null;
  }

  if (!hasContent) {
    return (
      <section className="space-y-2 border-t border-rule pt-6">
        <Kicker>Agent 評論</Kicker>
        <p className="font-sans text-meta text-ink-soft">尚無 Agent 評論。</p>
        <p className="font-sans text-kicker text-ink-faint">
          舊稿可能尚未經分析流程；新稿通常會在 pipeline 產出後顯示。
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4 border-t border-rule pt-6">
      <Kicker>Agent 評論</Kicker>
      <div className="space-y-4 font-sans text-editorial-body text-ink">
        {wh && (
          <div>
            <p className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-faint">
              事實
            </p>
            <p className="mt-1 whitespace-pre-line leading-[1.6]">{wh}</p>
          </div>
        )}
        {why && (
          <div>
            <p className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-faint">
              含義
            </p>
            <p className="mt-1 whitespace-pre-line leading-[1.6]">{why}</p>
          </div>
        )}
      </div>
    </section>
  );
}
