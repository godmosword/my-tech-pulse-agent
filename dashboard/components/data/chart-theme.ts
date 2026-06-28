/**
 * Shared chart theme — single source for recharts styling so tooltips, axes,
 * and grid lines stay consistent across every chart. All values resolve CSS
 * vars from globals.css, so light/dark flips the entire surface in one move.
 */

/** Tooltip container — theme-aware paper-tint card with a hairline border. */
export const TOOLTIP_CONTENT_STYLE = {
  background: "var(--color-paper-tint)",
  border: "1px solid var(--color-rule)",
  borderRadius: 8,
  fontSize: 13,
  color: "var(--color-ink)",
} as const;

/** Tooltip label row (the x-axis category line). */
export const TOOLTIP_LABEL_STYLE = { color: "var(--color-ink-soft)" } as const;

/** Tooltip value rows. */
export const TOOLTIP_ITEM_STYLE = { color: "var(--color-ink)" } as const;

/** Hairline grid + axis stroke. */
export const GRID_STROKE = "var(--color-rule)" as const;

/** Axis tick label — faint ink, small. */
export const AXIS_TICK = { fill: "var(--color-ink-faint)", fontSize: 11 } as const;

/** Categorical palette for multi-series charts. Mirrors `--chart-1..4`. */
export const CHART_SERIES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
] as const;
