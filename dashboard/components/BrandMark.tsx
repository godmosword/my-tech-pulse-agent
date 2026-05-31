import Link from "next/link";

type Props = {
  /** Mobile masthead uses slightly larger title on sm+. */
  variant?: "rail" | "mobile";
  className?: string;
};

export function BrandMark({ variant = "rail", className = "" }: Props) {
  const titleClass =
    variant === "mobile"
      ? "font-serif text-[28px] font-semibold tracking-[-0.02em] text-ink sm:text-[32px]"
      : "block font-serif text-[28px] font-semibold leading-none tracking-[-0.02em] text-ink";
  const subtitleMt = variant === "mobile" ? "mt-1" : "mt-2";

  return (
    <Link href="/" className={`block ${className}`.trim()}>
      <span className={titleClass}>Tech Pulse</span>
      <span
        className={`${subtitleMt} block font-sans text-meta font-semibold uppercase tracking-[0.1em] text-ink-soft`}
      >
        科技脈搏
      </span>
    </Link>
  );
}
