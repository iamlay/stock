import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StockCard, SustainBadge } from "@/components/stock-card";
import { StockSectionTabs } from "@/components/stock-section-tabs";
import { fetchStocks } from "@/lib/stocks";
import { fmtPct, trendClass } from "@/lib/format";

const SITE_URL = "https://stock.iamlay.com";
const PAGE_SIZE = 20;

type PageProps = {
  params: Promise<{ industry: string }>;
  searchParams: Promise<{ page?: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const raw = (await params).industry;
  const industry = decodeURIComponent(raw);
  const url = `${SITE_URL}/stocks/industry/${encodeURIComponent(industry)}`;
  return {
    title: `${industry}行业股票与股息率`,
    description: `浏览${industry}行业 A 股，按 TTM 股息率排序，查看最新价、市值、股息率与分红特征。`,
    keywords: [`${industry}行业`, `${industry}股票`, `${industry}股息率`],
    alternates: { canonical: url },
    openGraph: {
      title: `${industry}行业股票与股息率`,
      description: `浏览${industry}行业 A 股，按 TTM 股息率排序。`,
      url,
      siteName: "StockLab",
      type: "website",
      locale: "zh_CN",
    },
    robots: { index: true, follow: true },
  };
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

export default async function StockIndustryPage({
  params,
  searchParams,
}: PageProps) {
  const raw = (await params).industry;
  const industry = decodeURIComponent(raw);
  if (!industry || industry.length > 32) notFound();
  const page = Math.max(1, Number((await searchParams).page) || 1);

  const data = await fetchStocks({
    industry,
    sort: "dividend_yield_ttm",
    order: "desc",
    page,
    page_size: PAGE_SIZE,
  });
  if (!data) notFound();

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const url = `${SITE_URL}/stocks/industry/${encodeURIComponent(industry)}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${url}#page`,
        url,
        name: `${industry}行业股票`,
        description: `${industry}行业 A 股列表`,
        isPartOf: { "@type": "WebSite", name: "StockLab", url: SITE_URL },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "首页", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "高股息个股", item: `${SITE_URL}/stocks` },
          { "@type": "ListItem", position: 3, name: "行业", item: `${SITE_URL}/stocks/industry` },
          { "@type": "ListItem", position: 4, name: industry, item: url },
        ],
      },
    ],
  };

  function pageHref(target: number): string {
    return target > 1
      ? `/stocks/industry/${encodeURIComponent(industry)}?page=${target}`
      : `/stocks/industry/${encodeURIComponent(industry)}`;
  }

  return (
    <div className="space-y-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />
      <nav className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
        <Link href="/" className="hover:text-ink">首页</Link>
        <span>/</span>
        <Link href="/stocks" className="hover:text-ink">高股息个股</Link>
        <span>/</span>
        <Link href="/stocks/industry" className="hover:text-ink">行业</Link>
        <span>/</span>
        <span className="text-ink">{industry}</span>
      </nav>

      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
          Industry
        </p>
        <h1 className="mt-1 font-serif text-3xl text-ink">{industry}行业</h1>
        <p className="mt-1 text-sm text-muted">
          共 {data.total.toLocaleString("zh-CN")} 只 · 按 TTM 股息率排序
        </p>
      </div>

      <StockSectionTabs active="industry" />

      <div className="card overflow-hidden">
        {data.items.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted">
            该行业暂无已入库股票。
          </div>
        ) : (
          <>
            <div className="md:hidden">
              {data.items.map((stock) => (
                <StockCard key={stock.code} stock={stock} />
              ))}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-line bg-[#faf9f5] text-xs text-muted">
                  <tr>
                    <th className="px-4 py-3 font-normal">代码 / 名称</th>
                    <th className="px-4 py-3 text-right font-normal">最新价</th>
                    <th className="px-4 py-3 text-right font-normal">涨跌</th>
                    <th className="px-4 py-3 text-right font-normal">股息率 TTM</th>
                    <th className="px-4 py-3 text-right font-normal">年度股息率</th>
                    <th className="px-4 py-3 text-right font-normal">市值（亿）</th>
                    <th className="px-4 py-3 text-right font-normal">PE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.items.map((stock) => (
                    <tr key={stock.code} className="hover:bg-black/[0.02]">
                      <td className="px-4 py-3">
                        <Link href={`/stocks/${stock.code}`} className="group">
                          <span className="tnum text-xs text-muted">{stock.code}</span>
                          <span className="ml-2 text-ink group-hover:text-jade-deep">
                            {stock.name}
                          </span>
                          {stock.is_st ? (
                            <span className="ml-2 text-[10px] text-loss">ST</span>
                          ) : null}
                        </Link>
                      </td>
                      <td className="tnum px-4 py-3 text-right text-ink">
                        {stock.price?.toFixed(2) ?? "—"}
                      </td>
                      <td className={`tnum px-4 py-3 text-right ${stock.change_pct == null ? "text-muted" : trendClass(stock.change_pct)}`}>
                        {stock.change_pct == null ? "—" : fmtPct(stock.change_pct)}
                      </td>
                      <td className="tnum px-4 py-3 text-right">
                        <div className="text-jade-deep">{pct(stock.dividend_yield_ttm)}</div>
                        <SustainBadge value={stock.sustainability} />
                      </td>
                      <td className="tnum px-4 py-3 text-right text-ink-soft">
                        {pct(stock.dividend_yield_fy)}
                      </td>
                      <td className="tnum px-4 py-3 text-right text-ink-soft">
                        {stock.market_cap?.toFixed(0) ?? "—"}
                      </td>
                      <td className="tnum px-4 py-3 text-right text-ink-soft">
                        {stock.pe_ttm?.toFixed(1) ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-between text-xs text-muted">
          <span>第 {page} / {totalPages} 页</span>
          <div className="flex gap-2">
            {page > 1 ? (
              <Link href={pageHref(page - 1)} className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink">
                上一页
              </Link>
            ) : null}
            {page < totalPages ? (
              <Link href={pageHref(page + 1)} className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink">
                下一页
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      <p className="text-xs leading-6 text-muted">
        数据来自公开行情与分红记录，按 TTM 股息率排序；不构成投资建议。
      </p>
    </div>
  );
}
