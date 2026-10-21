import type { Metadata } from "next";
import Link from "next/link";

import { fetchStocks, type StockQuery } from "@/lib/stocks";
import { StockSearchBox } from "@/components/stock-search-box";
import { fmtPct, trendClass } from "@/lib/format";

export const metadata: Metadata = { title: "高股息个股" };
export const dynamic = "force-dynamic";

const SORTS = [
  ["dividend_yield_ttm", "股息率 TTM"],
  ["dividend_yield_fy", "年度股息率"],
  ["market_cap", "总市值"],
  ["change_pct", "涨跌幅"],
  ["pe_ttm", "PE"],
] as const;

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

function money(value: number | null): string {
  return value == null ? "—" : value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

const SUSTAIN: Record<string, { label: string; className: string; title: string }> = {
  stable: {
    label: "连续",
    className: "bg-jade-soft text-jade-deep",
    title: "连续 5 年以上分红，股息率不高于 8%",
  },
  watch: {
    label: "核查",
    className: "bg-amber-soft text-amber",
    title: "股息率偏高或 TTM 与年度差异较大，需核查",
  },
  one_off: {
    label: "单次大额",
    className: "bg-amber-soft text-amber",
    title: "含单次大额或特别分红，需判断可持续性",
  },
  high_yield: {
    label: "高股息",
    className: "bg-amber-soft text-amber",
    title: "TTM 股息率超过 15%，需核查一次性因素",
  },
  none: {
    label: "无分红",
    className: "bg-[#f1efe8] text-muted",
    title: "近两年没有实施现金分红",
  },
};

function SustainBadge({ value }: { value: string | null }) {
  if (!value || !SUSTAIN[value]) return null;
  const item = SUSTAIN[value];
  return (
    <span
      title={item.title}
      className={`mt-1 inline-block rounded-sm px-1.5 py-0.5 text-[10px] ${item.className}`}
    >
      {item.label}
    </span>
  );
}

export default async function StocksPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const sort = SORTS.some(([value]) => value === one(params.sort))
    ? one(params.sort)
    : "dividend_yield_ttm";
  const order = one(params.order) === "asc" ? "asc" : "desc";
  const q = one(params.q);
  const industry = one(params.industry);
  const minYieldRaw = one(params.min_yield);
  const minYield = minYieldRaw ? Number(minYieldRaw) : undefined;
  const includeSt = one(params.include_st) === "true";
  const page = Math.max(1, Number(one(params.page)) || 1);

  const query: StockQuery = {
    sort,
    order,
    q: q || undefined,
    industry: industry || undefined,
    min_yield: Number.isFinite(minYield) ? minYield : undefined,
    include_st: includeSt,
    page,
    page_size: 20,
  };
  const data = await fetchStocks(query);

  function pageHref(target: number): string {
    const search = new URLSearchParams();
    if (sort !== "dividend_yield_ttm") search.set("sort", sort);
    if (order !== "desc") search.set("order", order);
    if (q) search.set("q", q);
    if (industry) search.set("industry", industry);
    if (minYieldRaw) search.set("min_yield", minYieldRaw);
    if (includeSt) search.set("include_st", "true");
    search.set("page", String(target));
    return `/stocks?${search.toString()}`;
  }

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">Dividend Stocks</p>
          <h1 className="mt-1 font-serif text-3xl text-ink">高股息个股</h1>
          <p className="mt-1 text-sm text-muted">
            按 TTM 股息率排序 · 默认排除 ST · 日频数据，非实时行情
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StockSearchBox />
          <div className="text-right text-xs text-muted">
            <p className="tnum">共 {total.toLocaleString("zh-CN")} 只</p>
            <p>股息率 = 近 12 个月现金分红 / 不复权最新价</p>
          </div>
        </div>
      </div>

      <form
        method="get"
        action="/stocks"
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
            defaultValue={minYieldRaw}
            placeholder="如 3"
            className="w-24 rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted">排序</span>
          <select
            name="sort"
            defaultValue={sort}
            className="rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          >
            {SORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted">方向</span>
          <select
            name="order"
            defaultValue={order}
            className="rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          >
            <option value="desc">从高到低</option>
            <option value="asc">从低到高</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 pb-2 text-muted">
          <input type="checkbox" name="include_st" value="true" defaultChecked={includeSt} />
          包含 ST
        </label>
        <button
          type="submit"
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep"
        >
          筛选
        </button>
        <Link href="/stocks" className="pb-2 text-jade-deep hover:underline">
          重置
        </Link>
      </form>

      <div className="card overflow-hidden">
        {!data ? (
          <div className="p-8 text-center text-sm text-muted">
            个股数据暂不可用，请检查 API 服务与个股数据是否已同步。
          </div>
        ) : data.items.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted">没有符合条件的股票。</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-line bg-[#faf9f5] text-xs text-muted">
                <tr>
                  <th className="px-4 py-3 font-normal">代码 / 名称</th>
                  <th className="px-4 py-3 font-normal">行业</th>
                  <th className="px-4 py-3 text-right font-normal">最新价</th>
                  <th className="px-4 py-3 text-right font-normal">涨跌</th>
                  <th className="px-4 py-3 text-right font-normal">股息率 TTM</th>
                  <th className="px-4 py-3 text-right font-normal">年度股息率</th>
                  <th className="px-4 py-3 text-right font-normal">市值（亿）</th>
                  <th className="px-4 py-3 text-right font-normal">PE</th>
                  <th className="px-4 py-3 font-normal">最近除息</th>
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
                          <span className="ml-2 rounded-sm bg-loss/10 px-1.5 py-0.5 text-[10px] text-loss">
                            ST
                          </span>
                        ) : null}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-soft">
                      {stock.industry ?? "未分类"}
                    </td>
                    <td className="tnum px-4 py-3 text-right text-ink">
                      {stock.price == null ? "—" : stock.price.toFixed(2)}
                    </td>
                    <td
                      className={`tnum px-4 py-3 text-right ${
                        stock.change_pct == null ? "text-muted" : trendClass(stock.change_pct)
                      }`}
                    >
                      {stock.change_pct == null ? "—" : fmtPct(stock.change_pct)}
                    </td>
                    <td className="tnum px-4 py-3 text-right">
                      <div className="font-medium text-jade-deep">
                        {pct(stock.dividend_yield_ttm)}
                      </div>
                      <SustainBadge value={stock.sustainability} />
                    </td>
                    <td className="tnum px-4 py-3 text-right text-ink-soft">
                      {pct(stock.dividend_yield_fy)}
                    </td>
                    <td className="tnum px-4 py-3 text-right text-ink-soft">
                      {money(stock.market_cap)}
                    </td>
                    <td className="tnum px-4 py-3 text-right text-ink-soft">
                      {stock.pe_ttm == null ? "—" : stock.pe_ttm.toFixed(1)}
                    </td>
                    <td className="tnum px-4 py-3 text-xs text-muted">
                      {stock.last_ex_date ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
        股息率仅统计已除息的税前现金分红，特别分红会计入并标注；无分红显示“—”。数据不构成投资建议。
      </p>
    </div>
  );
}
