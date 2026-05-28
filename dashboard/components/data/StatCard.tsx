import { Delta } from "./Delta";
import { SourceTag } from "./SourceTag";

type Props = {
  kicker: string;
  value: string | number;
  unit?: string;
  delta?: number;
  footnote?: string;
  asOf?: string;
  source?: string;
  manual?: boolean;
  degraded?: boolean;
};

export function StatCard({
  kicker,
  value,
  unit,
  delta,
  footnote,
  asOf,
  source,
  manual,
  degraded,
}: Props) {
  return (
    <div className="section-band flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <p className="font-sans text-meta font-semibold uppercase tracking-[0.08em] text-ink-faint">
          {kicker}
        </p>
        {(asOf || source) && (
          <SourceTag source={source} asOf={asOf} manual={manual} degraded={degraded} />
        )}
      </div>
      <p className="stat-hero min-w-0 text-ink">
        {value}
        {unit && (
          <span className="ml-1 font-sans text-lg font-normal text-ink-soft">{unit}</span>
        )}
      </p>
      {delta != null && Number.isFinite(delta) && (
        <p className="font-sans text-meta">
          <Delta value={delta} />
        </p>
      )}
      {footnote && <p className="font-sans text-meta text-ink-soft">{footnote}</p>}
    </div>
  );
}
