/**
 * 1px hairline rule used as the section / item divider in place of card boxes.
 *
 * `weight="thick"` is for major section breaks (top of the page, between
 * top-level sections); default `thin` is the in-flow item separator.
 */
export function Hairline({
  weight = "thin",
  className,
}: {
  weight?: "thin" | "thick";
  className?: string;
}) {
  const height = weight === "thick" ? "h-px sm:h-0.5" : "h-px";
  return (
    <hr
      role="presentation"
      className={`${height} w-full border-0 bg-rule ${className ?? ""}`}
    />
  );
}
