type Segment = {
  label: string;
  pct: number;
  theme: string;
};

type Props = {
  segments: Segment[];
  concentrationThreshold?: number;
};

/** Rotating segment fills — all CSS-var based, no hardcoded hex. */
const SEGMENT_FILLS = [
  "bg-accent/50",
  "bg-info/50",
  "bg-pos/40",
  "bg-warn/40",
  "bg-ink-faint/30",
];

export function StackedExposureBar({
  segments,
  concentrationThreshold = 50,
}: Props) {
  const sorted = [...segments].sort((a, b) => b.pct - a.pct);
  const top = sorted[0];
  const concentrated = top && top.pct > concentrationThreshold;

  return (
    <div>
      <div
        className="flex h-3 w-full overflow-hidden rounded-full border border-rule"
        role="img"
        aria-label="主題曝險堆疊"
      >
        {sorted.map((seg, i) => (
          <div
            key={seg.theme}
            className={`h-full ${SEGMENT_FILLS[i % SEGMENT_FILLS.length]} ${
              concentrated && seg.theme === top.theme
                ? "ring-2 ring-inset ring-warn"
                : ""
            }`}
            style={{ width: `${Math.min(100, Math.max(0, seg.pct))}%` }}
            title={`${seg.label} ${seg.pct.toFixed(1)}%`}
          />
        ))}
      </div>
      <ul className="mt-3 space-y-1.5">
        {sorted.map((seg, i) => (
          <li
            key={seg.theme}
            className="flex items-center justify-between gap-2 font-sans text-meta text-ink-soft"
          >
            <span className="flex items-center gap-2">
              <span
                className={`inline-block h-2 w-2 shrink-0 rounded-sm ${SEGMENT_FILLS[i % SEGMENT_FILLS.length]}`}
              />
              <span className={concentrated && seg.theme === top.theme ? "font-semibold text-warn" : ""}>
                {seg.label}
                {concentrated && seg.theme === top.theme ? " · 集中" : ""}
              </span>
            </span>
            <span className="data-num">{seg.pct.toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
