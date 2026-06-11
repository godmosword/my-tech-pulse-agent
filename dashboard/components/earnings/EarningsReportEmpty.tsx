import Link from "next/link";

type Props = {
  ticker: string;
};

export function EarningsReportEmpty({ ticker }: Props) {
  return (
    <div className="section-band mt-6">
      <p className="font-serif text-editorial-headline text-ink">深度報告尚未就緒</p>
      <p className="mt-2 font-sans text-body text-ink-soft">
        此份財報的深度解析尚在產生中，或該季度資料不足以彙整完整敘述。您可先查看
        {" "}
        <Link
          href={`/earnings/${encodeURIComponent(ticker)}`}
          className="text-accent hover:underline"
        >
          {ticker} 財報總覽
        </Link>
        ，或待下次 pipeline 完成後再回來。
      </p>
    </div>
  );
}
