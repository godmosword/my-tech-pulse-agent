interface SparklineProps {
  /** Numeric points, oldest → newest. */
  values: number[];
  /** Accessible description of what the trend shows. */
  ariaLabel: string;
  /** CSS color (defaults to the chart-1 token). */
  color?: string;
  width?: number;
  height?: number;
  /** Highlight the latest point with a dot. */
  showEndDot?: boolean;
}

const DEFAULT_WIDTH = 64;
const DEFAULT_HEIGHT = 20;
const PAD = 2;

/**
 * Tiny inline trend line — zero dependencies, so list pages stay light (no
 * recharts bundle). Colors resolve `--chart-*` tokens and flip with the theme.
 * Renders nothing meaningful below two points.
 */
export function Sparkline({
  values,
  ariaLabel,
  color = "var(--chart-1)",
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  showEndDot = true,
}: SparklineProps) {
  const points = values.filter((v) => Number.isFinite(v));
  if (points.length < 2) return null;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1; // flat series → avoid divide-by-zero
  const stepX = (width - PAD * 2) / (points.length - 1);

  const coords = points.map((v, i) => {
    const x = PAD + i * stepX;
    // Invert Y: larger value sits higher on screen.
    const y = PAD + (1 - (v - min) / span) * (height - PAD * 2);
    return { x, y };
  });

  const path = coords
    .map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(2)},${c.y.toFixed(2)}`)
    .join(" ");
  const last = coords[coords.length - 1]!;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel}
      className="overflow-visible"
    >
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {showEndDot && <circle cx={last.x} cy={last.y} r={1.8} fill={color} />}
    </svg>
  );
}
