import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getItemById } from "@/lib/firestore";
import {
  categoryLabel,
  formatEditorialDate,
  formatMetaDate,
} from "@/lib/digest";
import { isPublicReadMode } from "@/lib/env-public-read";
import { publicSummaryLine } from "@/lib/public-excerpt";
import { getReaderSession } from "@/lib/session";
import { hasGatedLongContent } from "@/lib/zh-content";
import { DeepInsightCard } from "@/components/DeepInsightCard";
import { Hairline } from "@/components/Hairline";
import { Kicker, MetaDot } from "@/components/Kicker";

/** Build 階段無 Firestore 憑證時避免 prerender 失敗。 */
export const dynamic = "force-dynamic";

export const revalidate = 600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const item = await getItemById(decodeURIComponent(id));
  if (!item) {
    return { title: "找不到內容" };
  }
  const title = item.title || item.entity || "Untitled";
  const description =
    publicSummaryLine(item) || "科技脈搏專欄 — 技術、資本與矽谷的編輯視角。";
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "article",
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
  };
}

export default async function ItemPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const decodedId = decodeURIComponent(id);
  const item = await getItemById(decodedId);
  if (!item) notFound();

  const authenticated =
    !isPublicReadMode() || (await getReaderSession()) !== null;
  const returnToPath = `/item/${encodeURIComponent(decodedId)}`;
  const loginHref = `/login?returnTo=${encodeURIComponent(returnToPath)}`;
  const previewLine = publicSummaryLine(item);

  if (item.kind === "deep_brief") {
    return (
      <article className="space-y-10 pt-2">
        <DeepInsightCard
          item={item}
          authenticated={authenticated}
          returnToPath={returnToPath}
        />
        <Meta item={item} />
      </article>
    );
  }

  const headline = item.title || item.entity || "Untitled";
  const cat = categoryLabel(item.category);
  const metaDate = formatMetaDate(
    item.published_at_iso || item.delivered_at_iso
  );

  return (
    <article className="space-y-7 pt-2">
      <header className="space-y-5">
        <Kicker as="div" className="flex flex-wrap items-center">
          <span>{cat}</span>
          {item.source_name && (
            <>
              <MetaDot />
              <span>{item.source_name}</span>
            </>
          )}
          {metaDate && (
            <>
              <MetaDot />
              <span>{metaDate}</span>
            </>
          )}
        </Kicker>
        <h1 className="font-serif text-[34px] leading-[1.12] tracking-[-0.02em] text-ink sm:text-hero">
          {headline}
        </h1>
        <Hairline />
      </header>

      {authenticated ? (
        <>
          {item.zh_summary?.trim() && (
            <div className="space-y-2">
              <Kicker>導讀</Kicker>
              <p className="font-sans text-[18px] leading-[1.6] text-ink">
                {item.zh_summary}
              </p>
            </div>
          )}
          {item.zh_body?.trim() && (
            <div className="space-y-2">
              <Kicker>中文全文</Kicker>
              <p className="whitespace-pre-line font-serif text-[17px] leading-[1.7] text-ink">
                {item.zh_body}
              </p>
            </div>
          )}
          {item.summary?.trim() && (
            <div className="space-y-2 border-t border-rule pt-6">
              <Kicker>English summary</Kicker>
              <p className="whitespace-pre-line font-sans text-[16px] leading-[1.65] text-ink-soft">
                {item.summary}
              </p>
            </div>
          )}
        </>
      ) : (
        <>
          {previewLine && (
            <p className="font-sans text-[18px] leading-[1.6] text-ink">
              {previewLine}
            </p>
          )}
          {hasGatedLongContent(item) && (
            <p className="font-sans text-meta text-ink-soft">
              <Link
                href={loginHref}
                className="text-accent underline-offset-4 hover:underline"
              >
                登入以閱讀完整中文全文
              </Link>
            </p>
          )}
        </>
      )}

      <Meta item={item} />
    </article>
  );
}

function Meta({ item }: { item: Awaited<ReturnType<typeof getItemById>> }) {
  if (!item) return null;
  const rows: Array<{ label: string; value: string }> = [
    { label: "Kind", value: kindLabel(item.kind) },
    { label: "Category", value: item.category ? categoryLabel(item.category) : "—" },
    { label: "Entity", value: item.entity || "—" },
    { label: "Source", value: item.source_name || "—" },
    {
      label: "Published",
      value: formatEditorialDate(item.published_at_iso) || "—",
    },
    {
      label: "Delivered",
      value: formatEditorialDate(item.delivered_at_iso) || "—",
    },
  ];

  return (
    <section className="space-y-4 border-t border-rule pt-6">
      <Kicker>Provenance</Kicker>
      <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
        {rows.map(({ label, value }) => (
          <Row key={label} label={label} value={value} />
        ))}
      </dl>
      {item.source_url ? (
        <div>
          <dt className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
            Original
          </dt>
          <dd className="mt-1">
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
              className="break-all font-sans text-body text-accent underline-offset-4 hover:underline"
            >
              {item.source_url}
            </a>
          </dd>
        </div>
      ) : null}
    </section>
  );
}

function kindLabel(kind: "instant_summary" | "deep_brief" | "earnings"): string {
  switch (kind) {
    case "deep_brief":
      return "Deep Insight";
    case "earnings":
      return "Earnings";
    default:
      return "Dispatch";
  }
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft">
        {label}
      </dt>
      <dd className="mt-1 font-sans text-body text-ink">{value}</dd>
    </div>
  );
}
