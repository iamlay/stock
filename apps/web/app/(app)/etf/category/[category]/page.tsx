import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { EtfTable } from "@/components/etf-table";
import { fetchEtfs, toEtf } from "@/lib/api";
import { categories, type EtfCategory } from "@/lib/mock";

const SITE_URL = "https://stock.iamlay.com";
const PAGE_SIZE = 20;

type PageProps = {
  params: Promise<{ category: string }>;
  searchParams: Promise<{ page?: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const raw = (await params).category;
  const category = decodeURIComponent(raw);
  const url = `${SITE_URL}/etf/category/${encodeURIComponent(category)}`;
  return {
    title: `${category} ETF 列表与行情`,
    description: `浏览${category}类 ETF，查看最新价、涨跌、规模、估值分位与股息率。`,
    keywords: [`${category} ETF`, `${category}基金`, "ETF 列表"],
    alternates: { canonical: url },
    openGraph: {
      title: `${category} ETF 列表与行情`,
      description: `浏览${category}类 ETF 的行情、规模与估值。`,
      url,
      siteName: "StockLab",
      type: "website",
      locale: "zh_CN",
    },
    robots: { index: true, follow: true },
  };
}

export default async function EtfCategoryPage({ params, searchParams }: PageProps) {
  const raw = (await params).category;
  const category = decodeURIComponent(raw) as EtfCategory;
  if (!categories.includes(category)) notFound();
  const page = Math.max(1, Number((await searchParams).page) || 1);

  const apiEtfs = await fetchEtfs();
  const rows = (apiEtfs ?? []).map(toEtf).filter((item) => item.category === category);
  if (rows.length === 0) notFound();

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const pageRows = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const url = `${SITE_URL}/etf/category/${encodeURIComponent(category)}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${url}#page`,
        url,
        name: `${category} ETF`,
        isPartOf: { "@type": "WebSite", name: "StockLab", url: SITE_URL },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "首页", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "ETF 数据", item: `${SITE_URL}/etf` },
          { "@type": "ListItem", position: 3, name: "分类", item: `${SITE_URL}/etf/category` },
          { "@type": "ListItem", position: 4, name: category, item: url },
        ],
      },
    ],
  };

  function pageHref(target: number): string {
    return target > 1
      ? `/etf/category/${encodeURIComponent(category)}?page=${target}`
      : `/etf/category/${encodeURIComponent(category)}`;
  }

  return (
    <div className="space-y-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />
      <nav className="flex items-center gap-1.5 text-xs text-muted">
        <Link href="/etf" className="hover:text-ink">ETF 数据</Link>
        <span>/</span>
        <Link href="/etf/category" className="hover:text-ink">分类</Link>
        <span>/</span>
        <span className="text-ink">{category}</span>
      </nav>
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
          ETF Category
        </p>
        <h1 className="mt-1 font-serif text-3xl text-ink">{category} ETF</h1>
        <p className="mt-1 text-sm text-muted">
          共 {rows.length} 只 · 数据来自最新 ETF 行情
        </p>
      </div>

      <div className="card p-2 sm:p-4">
        <EtfTable rows={pageRows} />
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-between text-xs text-muted">
          <span>第 {current} / {totalPages} 页</span>
          <div className="flex gap-2">
            {current > 1 ? (
              <Link href={pageHref(current - 1)} className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink">
                上一页
              </Link>
            ) : null}
            {current < totalPages ? (
              <Link href={pageHref(current + 1)} className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink">
                下一页
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
