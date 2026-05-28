type Props = {
  source?: string;
  asOf?: string;
  degraded?: boolean;
  manual?: boolean;
  className?: string;
};

function dotClass(degraded?: boolean, manual?: boolean): string {
  if (manual) return "bg-warn";
  if (degraded) return "bg-warn";
  return "bg-info";
}

function tooltipText(props: Props): string {
  const parts: string[] = [];
  if (props.manual) parts.push("人工維護資料");
  if (props.degraded) parts.push("資料品質降級");
  if (props.source) parts.push(`來源：${props.source}`);
  if (props.asOf) parts.push(`截至 ${props.asOf}`);
  return parts.join(" · ") || "資料來源";
}

export function SourceTag({ source, asOf, degraded, manual, className = "" }: Props) {
  const label = asOf ? `截至 ${asOf}` : source ?? "—";
  const suffix = manual ? " · 人工" : degraded ? " · 降級" : "";

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-sans text-meta text-ink-faint ${className}`}
      title={tooltipText({ source, asOf, degraded, manual })}
    >
      <span
        className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${dotClass(degraded, manual)}`}
        aria-hidden
      />
      <span>
        {label}
        {suffix}
      </span>
    </span>
  );
}
