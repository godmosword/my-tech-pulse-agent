type Props = {
  value: number;
  suffix?: string;
  /** Show ↑ / ↓ arrows (default true). */
  showArrow?: boolean;
};

export function Delta({ value, suffix = "%", showArrow = true }: Props) {
  const formatted = `${value > 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
  if (value === 0 || Object.is(value, -0)) {
    return <span className="data-num text-ink-faint">{formatted}</span>;
  }
  const cls = value > 0 ? "delta-pos" : "delta-neg";
  const arrow = showArrow ? (value > 0 ? " ↑" : " ↓") : "";
  return (
    <span className={`data-num ${cls}`}>
      {formatted}
      {arrow}
    </span>
  );
}
