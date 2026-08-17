import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getItemById, listLatestItems } from "@/lib/firestore";
import {
  categoryLabel,
  formatEditorialDate,
  formatMetaDate,
} from "@/lib/digest";
import { isPublicReadMode } from "@/lib/env-public-read";
import { englishExcerpt, publicSummaryLine } from "@/lib/public-excerpt";
import { getReaderSession } from "@/lib/session";
import {
  bilingualEnglishSummary,
  bilingualEnglishTitle,
  chineseAbstract,
  hasGatedLongContent,
  shouldShowBilingualCompare,
} from "@/lib/zh-content";
import { pickRelatedItems } from "@/lib/related-items";
import { displayTitle, type RenderableItem } from "@/lib/types";
import { BilingualCompare } from "@/components/BilingualCompare";
import { DeepInsightCard } from "@/components/DeepInsightCard";
import { AgentCommentary } from "@/components/AgentCommentary";
import { BackLink } from "@/components/BackLink";
import { Breadcrumb } from "@/components/Breadcrumb";
import { NewsTakeawayBlock } from "@/components/NewsTakeawayBlock";
import { tagItemPortfolioRelevance } from "@/lib/portfolio-relevance";
import { LoginToReadCta } from "@/components/LoginToReadCta";
import { Hairline } from "@/components/Hairline";
import { Kicker, MetaDot } from "@/components/Kicker";
import { TickerQuote } from "@/components/data/TickerQuote";

/** Avoid static prerender of live item JSON. */
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
  const title = displayTitle(item);
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

  const latestItems = await listLatestItems({ limit: 60 });
  const relatedItems = pickRelatedItems(item, latestItems);

  const authenticated =
    !isPublicReadMode() || (await getReaderSession()) !== null;
  const returnToPath = `/item/${encodeURIComponent(decodedId)}`;

  if (item.kind === "deep_brief") {
    return (
      <article className="space-y-10 pt-2">
        <BackLink href="/" label="返回 Today" />
        <Breadcrumb items={[{ label: "Today", href: "/" }, { label: "文章" }]} />
        <DeepInsightCard
          item={item}
          authenticated={authenticated}
          returnToPath={returnToPath}
        />
        <RelatedReading items={relatedItems} />
        <Meta item={item} />
      </article>
    );
  }

  const zhTitle = displayTitle(item);
  const zhAbstract = authenticated
    ? chineseAbstract(item)
    : item.zh_summary?.trim() || "";
  const enTitle = bilingualEnglishTitle(item);
  const enSummaryRaw = bilingualEnglishSummary(item);
  const englishSummary = enSummaryRaw
    ? authenticated
      ? enSummaryRaw
      : englishExcerpt(enSummaryRaw)
    : "";
  const cat = categoryLabel(item.category);
  const tickers = item.tickers ?? [];
  const metaDate = formatMetaDate(
    item.published_at_iso || item.delivered_at_iso
  );

  return (
    <article className="space-y-7 pt-2">
      <BackLink href="/" label="返回 Today" />
      <Breadcrumb items={[{ label: "Today", href: "/" }, { label: "文章" }]} />
      <header className="space-y-5">
        <Kicker as="div" className="flex flex-wrap items-center">
          <span>{cat}</span>
          {item.source_name && (
            <>
              <MetaDot />
              {item.source_url ? (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent underline-offset-4 hover:underline"
                >
                  {item.source_name}
                </a>
              ) : (
                <span>{item.source_name}</span>
              )}
            </>
          )}
          {metaDate && (
            <>
              <MetaDot />
              <span>{metaDate}</span>
            </>
          )}
        </Kicker>
        <div className="space-y-2">
          <Kicker>中文標題</Kicker>
          <h1 className="font-serif text-editorial-title text-ink sm:text-hero">
            {zhTitle}
          </h1>
        </div>
        <Hairline />
      </header>

      {zhAbstract ? (
        <div className="space-y-2">
          <Kicker>中文摘要</Kicker>
          <p className="editorial-dropcap whitespace-pre-line font-sans text-editorial-body text-ink">
            {zhAbstract}
          </p>
        </div>
      ) : authenticated ? (
        <p className="font-sans text-meta text-ink-soft">尚無中文摘要。</p>
      ) : null}

      <AgentCommentary
        whatHappened={item.what_happened}
        whyItMatters={item.why_it_matters}
        authenticated={authenticated}
      />

      {item.takeaway && authenticated && (
        <NewsTakeawayBlock
          takeaway={item.takeaway}
          relevance={tagItemPortfolioRelevance(item.takeaway.tickers)}
        />
      )}

      {!authenticated && hasGatedLongContent(item) && (
        <LoginToReadCta returnToPath={returnToPath} />
      )}

      {shouldShowBilingualCompare(item) && (enTitle || englishSummary) && (
        <BilingualCompare
          englishTitle={enTitle}
          englishSummary={englishSummary || null}
          presentation="stacked"
        />
      )}

      {tickers.length > 0 && (
        <div
          aria-label={`相關代號：${tickers.join(", ")}`}
          className="flex flex-wrap items-center gap-1.5 font-sans text-kicker font-semibold uppercase tracking-[0.12em] text-ink-soft"
        >
          <span className="text-ink-faint">代號</span>
          {tickers.map((t) => (
            <TickerQuote key={t} ticker={t} />
          ))}
        </div>
      )}

      <RelatedReading items={relatedItems} />
      <Meta item={item} />
    </article>
  );
}

function RelatedReading({ items }: { items: RenderableItem[] }) {
  if (items.length === 0) return null;

  return (
    <section className="space-y-4">
      <Kicker>相關閱讀</Kicker>
      <Hairline />
      <ul className="divide-y divide-rule">
        {items.map((related) => (
          <li key={related.id} className="py-4">
            <Link
              href={`/item/${encodeURIComponent(related.id)}`}
              className="font-serif text-dek leading-snug text-ink hover:text-accent"
            >
              {displayTitle(related)}
            </Link>
          </li>
        ))}
      </ul>
    </section>
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
