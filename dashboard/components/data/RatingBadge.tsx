export type SignalRating =
  | "強力看多"
  | "看多"
  | "中性"
  | "看空"
  | "強力看空"
  | "資料不足";

type Props = {
  rating: SignalRating | string;
  conviction?: "high" | "medium" | "low" | string;
};

function ratingStyles(rating: string): string {
  if (rating === "強力看多" || rating === "看多") {
    return "border-pos/40 bg-pos-bg text-pos";
  }
  if (rating === "強力看空" || rating === "看空") {
    return "border-neg/40 bg-neg-bg text-neg";
  }
  if (rating === "中性") {
    return "border-info/40 bg-info-bg text-info";
  }
  return "border-rule bg-paper text-ink-faint";
}

export function RatingBadge({ rating, conviction }: Props) {
  const lowConviction = conviction === "low";
  return (
    <span
      className={`inline-flex items-center rounded border px-2.5 py-0.5 font-sans text-meta font-semibold ${ratingStyles(
        rating,
      )} ${lowConviction ? "border-dashed opacity-60" : ""}`}
      title={lowConviction ? "低信心 — 因子覆蓋不足，僅供參考" : undefined}
    >
      {rating}
    </span>
  );
}
