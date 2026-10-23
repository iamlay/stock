import type { Metadata } from "next";
import Link from "next/link";

import { StockSearchBox } from "@/components/stock-search-box";
import { StockSectionTabs } from "@/components/stock-section-tabs";
import { buildGrid, GRID_YIELDS, type StockGrid } from "@/lib/grid";
import { fetchStocks, type Stock, type StockQuery } from "@/lib/stocks";

export const metadata: Metadata = { title: "股息网格" };
export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

function targetClass(stock: Stock, targetPrice: number): string {
  if (stock.price == null) return "text-muted";
  return targetPrice <= stock.price ? "text-jade-deep" : "text-ink-soft";
}

function GridCard({ stock, grid }: { stock: Stock; grid: StockGrid }) {
  return (
    <article className="border-b border-line p-4 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href={`/stocks/${stock.code}?tab=grid`} className="group">
            <span className="text-ink group-hover:text-jade-deep">{stock.name}</span>
            <span className="tnum ml-2 text-xs text-muted">{stock.code}</span>
          </Link>
          <p className="mt-1 text-xs text-muted">{stock.industry ?? "未分类"}</p>
        </div>
        <div className="text-right">
          <p className="tnum text-sm text-ink">{stock.price?.toFixed(2) ?? "—"}</p>
          <p className="tnum text-xs text-jade-deep">{pct(stock.dividend_yield_ttm)}</p>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-5 gap-1.5">
        {grid.targets.map((target) => (
          <div key={target.yield} className="rounded-sm bg-paper/70 px-1.5 py-2 text-center">
            <p className="text-[10px] text-muted">{target.yield}%</p>
            <p className={`tnum mt-0.5 text-xs ${targetClass(stock, target.price)}`}>
              {target.price.toFixed(2)}
            </p>
            <p className="tnum mt-0.5 text-[10px] text-muted">
              {target.distancePct > 0 ? "+" : ""}
              {target.distancePct.toFixed(1)}%
            </p>
          </div>
        ))}
      </div>
    </article>
  );
}

export default async function StockGridPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const q = one(params.q);
  const industry = one(params.industry);
  const minYieldRaw = one(params.min_yield);
  const minYield = minYieldRaw ? Number(minYieldRaw) : 0.01;
  const page = Math.max(1, Number(one(params.page)) || 1);

  const query: StockQuery = {
    sort: "dividend_yield_ttm",
    order: "desc",
    q: q || undefined,
    industry: industry || undefined,
    min_yield: Number.isFinite(minYield) ? minYield : 0.01,
    page,
    page_size: PAGE_SIZE,
  };
  const data = await fetchStocks(query);
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const rows = (data?.items ?? [])
    .map((stock) => ({ stock, grid: buildGrid(stock.price, stock.dividend_yield_ttm) }))
    .filter((row): row is { stock: Stock; grid: StockGrid } => row.grid !== null);

  function pageHref(target: number): string {
    const search = new URLSearchParams();
    if (q) search.set("q", q);
    if (industry) search.set("industry", industry);
    if (minYieldRaw) search.set("min_yield", minYieldRaw);
    search.set("page", String(target));
    return `/stocks/grid?${search.toString()}`;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
            Dividend Grid
          </p>
          <h1 className="mt-1 font-serif text-3xl text-ink">股息网格</h1>
          <p className="mt-1 text-sm text-muted">
            用近 12 个月现金分红倒推目标股息率价格 · 非实时行情
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StockSearchBox />
          <div className="text-right text-xs text-muted">
            <p className="tnum">共 {total.toLocaleString("zh-CN")} 只</p>
            <p>目标价 = 每股现金分红 / 目标股息率</p>
          </div>
        </div>
      </div>

      <StockSectionTabs active="grid" />

      <form
        method="get"
        action="/stocks/grid"
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
        <label className="flex flex-col gap-1">
          <span className="text-muted">最低股息率</span>
          <input
            name="min_yield"
            type="number"
            min="0"
            max="30"
            step="0.1"
            defaultValue={minYieldRaw || "0.1"}
            className="w-24 rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          />
        </label>
        <button
          type="submit"
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep"
        >
          筛选
        </button>
        <Link href="/stocks/grid" className="pb-2 text-jade-deep hover:underline">
          重置
        </Link>
      </form>

      <div className="card overflow-hidden">
        {!data ? (
          <div className="p-8 text-center text-sm text-muted">
            个股数据暂不可用，请检查 API 服务与个股数据是否已同步。
          </div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted">
            当前筛选下没有可计算网格的股票。无现金分红时无法倒推目标价。
          </div>
        ) : (
          <>
            <div className="md:hidden">
              {rows.map(({ stock, grid }) => (
                <GridCard key={stock.code} stock={stock} grid={grid} />
              ))}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="border-b border-line bg-[#faf9f5] text-xs text-muted">
                  <tr>
                    <th className="px-4 py-3 font-normal">代码 / 名称</th>
                    <th className="px-4 py-3 font-normal">行业</th>
                    <th className="px-4 py-3 text-right font-normal">现价</th>
                    <th className="px-4 py-3 text-right font-normal">股息率</th>
                    {GRID_YIELDS.map((target) => (
                      <th key={target} className="px-4 py-3 text-right font-normal">
                        {target}%
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map(({ stock, grid }) => (
                    <tr key={stock.code} className="hover:bg-black/[0.02]">
                      <td className="px-4 py-3">
                        <Link href={`/stocks/${stock.code}?tab=grid`} className="group">
                          <span className="tnum text-xs text-muted">{stock.code}</span>
                          <span className="ml-2 text-ink group-hover:text-jade-deep">
                            {stock.name}
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-xs text-ink-soft">
                        {stock.industry ?? "未分类"}
                      </td>
                      <td className="tnum px-4 py-3 text-right text-ink">
                        {stock.price?.toFixed(2) ?? "—"}
                      </td>
                      <td className="tnum px-4 py-3 text-right text-jade-deep">
                        {pct(grid.currentYield)}
                      </td>
                      {grid.targets.map((target) => (
                        <td
                          key={target.yield}
                          className={`tnum px-4 py-3 text-right ${targetClass(stock, target.price)}`}
                        >
                          <div>{target.price.toFixed(2)}</div>
                          <div className="text-[10px] text-muted">
                            {target.distancePct > 0 ? "+" : ""}
                            {target.distancePct.toFixed(1)}%
                          </div>
                        </td>
                      ))}
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
        网格目标价按“近 12 个月已除息现金分红 ÷ 目标股息率”计算；分红下降或特别分红会导致目标价失真，
        不构成投资建议。绿色表示当前股息率已达到该档。
      </p>
    </div>
  );
}
