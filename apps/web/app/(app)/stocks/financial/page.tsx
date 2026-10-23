import type { Metadata } from "next";
import Link from "next/link";

import { StockSearchBox } from "@/components/stock-search-box";
import { StockSectionTabs } from "@/components/stock-section-tabs";
import {
  fetchStockFinancials,
  type AnnualFinancial,
  type StockFinancialSummary,
} from "@/lib/stocks";

export const metadata: Metadata = { title: "股息财务" };
export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

const PERIOD_LABELS: Record<string, string> = {
  Q1: "一季报",
  H1: "中报",
  Q3: "三季报",
  FY: "年报",
};

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function yi(value: number | null): string {
  return value == null ? "—" : (value / 100_000_000).toFixed(1);
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

function yoyClass(value: number | null): string {
  if (value == null) return "text-muted";
  return value >= 0 ? "text-loss" : "text-jade";
}

function AnnualCell({ item }: { item: AnnualFinancial | undefined }) {
  if (!item) return <span className="text-xs text-muted">—</span>;
  return (
    <div className="text-right">
      <p className="tnum text-xs text-ink">{yi(item.net_profit)}</p>
      <p className={`tnum text-[10px] ${yoyClass(item.net_profit_yoy)}`}>
        {item.net_profit_yoy == null
          ? "—"
          : `${item.net_profit_yoy > 0 ? "+" : ""}${item.net_profit_yoy.toFixed(1)}%`}
      </p>
    </div>
  );
}

function FinancialCard({ stock }: { stock: StockFinancialSummary }) {
  return (
    <article className="border-b border-line p-4 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href={`/stocks/${stock.code}?tab=financial`} className="group">
            <span className="text-ink group-hover:text-jade-deep">{stock.name}</span>
            <span className="tnum ml-2 text-xs text-muted">{stock.code}</span>
          </Link>
          <p className="mt-1 text-xs text-muted">{stock.industry ?? "未分类"}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-muted">
            {PERIOD_LABELS[stock.latest_period ?? ""] ?? "最新"}
          </p>
          <p className="tnum text-sm text-ink">{yi(stock.latest_net_profit)} 亿</p>
          <p className={`tnum text-[10px] ${yoyClass(stock.latest_net_profit_yoy)}`}>
            {stock.latest_net_profit_yoy == null
              ? "—"
              : `${stock.latest_net_profit_yoy > 0 ? "+" : ""}${stock.latest_net_profit_yoy.toFixed(1)}%`}
          </p>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-1.5">
        {stock.annuals.map((item) => (
          <div key={item.year} className="rounded-sm bg-paper/70 px-2 py-1.5 text-center">
            <p className="text-[10px] text-muted">{item.year}</p>
            <p className="tnum text-xs text-ink">{yi(item.net_profit)}</p>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-muted">
        披露日 {stock.disclosure_date ?? "—"}
      </p>
    </article>
  );
}

export default async function StockFinancialPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const q = one(params.q);
  const industry = one(params.industry);
  const page = Math.max(1, Number(one(params.page)) || 1);

  const data = await fetchStockFinancials({
    q: q || undefined,
    industry: industry || undefined,
    page,
    page_size: PAGE_SIZE,
  });
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function pageHref(target: number): string {
    const search = new URLSearchParams();
    if (q) search.set("q", q);
    if (industry) search.set("industry", industry);
    search.set("page", String(target));
    return `/stocks/financial?${search.toString()}`;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
            Financials
          </p>
          <h1 className="mt-1 font-serif text-3xl text-ink">股息财务</h1>
          <p className="mt-1 text-sm text-muted">
            年报 / 季报净利润与同比 · 先覆盖高股息前 500 只
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StockSearchBox />
          <div className="text-right text-xs text-muted">
            <p className="tnum">共 {total.toLocaleString("zh-CN")} 只</p>
            <p>净利润单位：亿元</p>
          </div>
        </div>
      </div>

      <StockSectionTabs active="financial" />

      <form
        method="get"
        action="/stocks/financial"
        className="card flex flex-wrap items-end gap-3 p-4 text-xs"
      >
        <label className="flex flex-col gap-1">
          <span className="text-muted">搜索</span>
          <input
            name="q"
            defaultValue={q}
            placeholder="代码或名称"
            className="w-36 rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted">行业</span>
          <input
            name="industry"
            defaultValue={industry}
            placeholder="如 金融"
            className="w-28 rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          />
        </label>
        <button
          type="submit"
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep"
        >
          筛选
        </button>
        <Link href="/stocks/financial" className="pb-2 text-jade-deep hover:underline">
          重置
        </Link>
      </form>

      <div className="card overflow-hidden">
        {!data ? (
          <div className="p-8 text-center text-sm text-muted">
            财务数据暂不可用，请确认 API 已部署且已执行 `stock-financials`。
          </div>
        ) : data.items.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted">
            暂无财务数据。先在 API 环境执行：
            <code className="mx-1 rounded bg-black/5 px-1">python -m etl.cli stock-financials --limit 500</code>
          </div>
        ) : (
          <>
            <div className="md:hidden">
              {data.items.map((stock) => (
                <FinancialCard key={stock.code} stock={stock} />
              ))}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="border-b border-line bg-[#faf9f5] text-xs text-muted">
                  <tr>
                    <th className="px-4 py-3 font-normal">代码 / 名称</th>
                    <th className="px-4 py-3 font-normal">行业</th>
                    <th className="px-4 py-3 text-right font-normal">最新报告</th>
                    <th className="px-4 py-3 text-right font-normal">净利润</th>
                    <th className="px-4 py-3 text-right font-normal">同比</th>
                    <th className="px-4 py-3 text-right font-normal">年度 1</th>
                    <th className="px-4 py-3 text-right font-normal">年度 2</th>
                    <th className="px-4 py-3 text-right font-normal">年度 3</th>
                    <th className="px-4 py-3 text-right font-normal">披露日</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.items.map((stock) => (
                    <tr key={stock.code} className="hover:bg-black/[0.02]">
                      <td className="px-4 py-3">
                        <Link href={`/stocks/${stock.code}?tab=financial`} className="group">
                          <span className="tnum text-xs text-muted">{stock.code}</span>
                          <span className="ml-2 text-ink group-hover:text-jade-deep">
                            {stock.name}
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-xs text-ink-soft">
                        {stock.industry ?? "未分类"}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-ink-soft">
                        {PERIOD_LABELS[stock.latest_period ?? ""] ?? "—"}
                        <span className="ml-1 text-[10px] text-muted">
                          {stock.latest_report_date?.slice(0, 10) ?? ""}
                        </span>
                      </td>
                      <td className="tnum px-4 py-3 text-right text-ink">
                        {yi(stock.latest_net_profit)}
                      </td>
                      <td
                        className={`tnum px-4 py-3 text-right text-xs ${yoyClass(stock.latest_net_profit_yoy)}`}
                      >
                        {stock.latest_net_profit_yoy == null
                          ? "—"
                          : `${stock.latest_net_profit_yoy > 0 ? "+" : ""}${stock.latest_net_profit_yoy.toFixed(1)}%`}
                      </td>
                      {[0, 1, 2].map((index) => (
                        <td key={index} className="px-4 py-3">
                          <AnnualCell item={stock.annuals[index]} />
                          <p className="tnum mt-0.5 text-right text-[10px] text-muted">
                            {stock.annuals[index]?.year ?? ""}
                          </p>
                        </td>
                      ))}
                      <td className="tnum px-4 py-3 text-right text-xs text-muted">
                        {stock.disclosure_date ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {data && totalPages > 1 ? (
        <div className="flex items-center justify-between text-xs text-muted">
          <span>
            第 {page} / {totalPages} 页
          </span>
          <div className="flex gap-2">
            {page > 1 ? (
              <Link
                href={pageHref(page - 1)}
                className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink"
              >
                上一页
              </Link>
            ) : null}
            {page < totalPages ? (
              <Link
                href={pageHref(page + 1)}
                className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink"
              >
                下一页
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      <p className="text-xs leading-6 text-muted">
        数据来自公开财报，净利润为归母净利润，单位亿元；同比为报告期同比。
        财报有滞后，不构成投资建议。
      </p>
    </div>
  );
}
