type Props = {
  label: string;
  surprise: number | null | undefined;
  basis?: string | null;
};

export function SurpriseBadge({ label, surprise, basis }: Props) {
  if (basis === "Mixed") {
    return (
      <span className="rounded px-2 py-0.5 font-sans text-meta bg-warn-bg text-warn">
        {label} · 基準不一致
      </span>
    );
  }

  if (surprise == null || !Number.isFinite(surprise)) {
    return null;
  }

  const tone =
    surprise > 0 ? "pos" : surprise < 0 ? "neg" : "warn";
  const toneClass =
    tone === "pos"
      ? "bg-pos-bg text-pos"
      : tone === "neg"
        ? "bg-neg-bg text-neg"
        : "bg-warn-bg text-warn";

  return (
    <span
      className={`rounded px-2 py-0.5 font-mono text-meta ${toneClass}`}
    >
      {label} {surprise > 0 ? "+" : ""}
      {surprise.toFixed(1)}%
    </span>
  );
}
