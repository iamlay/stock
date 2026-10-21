import type { Metadata } from "next";
import Link from "next/link";

import { EtfTable } from "@/components/etf-table";
import { EtfSortSelect } from "@/components/etf-sort-select";
import { fetchEtfs, toEtf } from "@/lib/api";
import { categories, etfs, type EtfCategory } from "@/lib/mock";

export const metadata: Metadata = { title: "ETF 数据" };
export const revalidate = 60;

export default async function EtfListPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; q?: string; page?: string; sort?: string }>;
}) {
  const { category, q, page, sort: rawSort } = await searchParams;
  const active = categories.includes(category as EtfCategory) ? (category as EtfCategory) : null;
  const term = (q ?? "").trim().toLowerCase();
  const pageNum = Math.max(1, Number(page) || 1);
  const sort = ["aum", "change", "yield", "code"].includes(rawSort ?? "")
    ? rawSort!
    : "aum";
  const PAGE_SIZE = 20;

  const apiEtfs = await fetchEtfs();
  const live = Boolean(apiEtfs && apiEtfs.length > 0);
  const all = apiEtfs && apiEtfs.length > 0 ? apiEtfs.map(toEtf) : etfs;
  const filtered = all
    .filter((etf) => (active ? etf.category === active : true))
    .filter((etf) =>
      term
        ? etf.code.toLowerCase().includes(term) || etf.name.toLowerCase().includes(term)
        : true,
    )
    .sort((a, b) => {
      if (sort === "change") return b.change - a.change;
      if (sort === "yield") return (b.dividendYield ?? -1) - (a.dividendYield ?? -1);
      if (sort === "code") return a.code.localeCompare(b.code);
      return (b.aum ?? 0) - (a.aum ?? 0);
    });
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(pageNum, totalPages);
  const rows = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const totalAum = filtered.reduce((sum, etf) => sum + (etf.aum ?? 0), 0);
  const dataDate = apiEtfs?.[0]?.trade_date ?? null;
  const quoteTime = apiEtfs?.[0]?.quote_time ?? null;

  function pageHref(target: number): string {
    const search = new URLSearchParams();
    if (active) search.set("category", active);
    if (term) search.set("q", term);
    if (sort !== "aum") search.set("sort", sort);
    search.set("page", String(target));
    return `/etf?${search.toString()}`;
  }

  function countFor(categoryName?: EtfCategory): number {
    return categoryName
      ? all.filter((etf) => etf.category === categoryName).length
      : all.length;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">ETF 数据</h1>
          <p className="mt-1 text-sm text-muted">100 只精选标的 · 红利 / 现金流 / 跨境 / 宽基 / 行业 / 债券 / 商品 / 货币</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/etf/compare"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            对比
          </Link>
          <EtfSortSelect value={sort} category={active ?? undefined} query={term || undefined} />
          <p className="tnum text-xs text-muted">
            {filtered.length} 只 · 合计规模 {totalAum.toFixed(0)} 亿 ·{" "}
            {live
              ? `数据 ${dataDate}${quoteTime ? ` · 更新 ${quoteTime.slice(11, 16)}` : ""}`
              : "示例数据"}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link
          href="/etf"
          className={`rounded-sm border px-3 py-1.5 text-xs transition-colors ${
            active === null
              ? "border-ink bg-ink text-paper"
              : "border-line bg-surface text-ink-soft hover:border-ink"
          }`}
        >
          全部 ({countFor()})
        </Link>
        {categories.map((item) => (
          <Link
            key={item}
            href={`/etf?category=${encodeURIComponent(item)}${sort !== "aum" ? `&sort=${sort}` : ""}`}
            className={`rounded-sm border px-3 py-1.5 text-xs transition-colors ${
              active === item
                ? "border-ink bg-ink text-paper"
                : "border-line bg-surface text-ink-soft hover:border-ink"
            }`}
          >
            {item} ({countFor(item)})
          </Link>
        ))}
      </div>

      <form method="get" action="/etf" className="flex flex-wrap items-center gap-2">
        {active ? <input type="hidden" name="category" value={active} /> : null}
        {sort !== "aum" ? <input type="hidden" name="sort" value={sort} /> : null}
        <input
          name="q"
          defaultValue={q ?? ""}
          placeholder="搜索代码或名称"
          className="w-56 rounded-sm border border-line bg-surface px-3 py-2 text-sm text-ink"
        />
        <button
          type="submit"
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper"
        >
          搜索
        </button>
        {term ? (
          <Link href={active ? `/etf?category=${encodeURIComponent(active)}` : "/etf"} className="text-xs text-jade-deep hover:underline">
            清除
          </Link>
        ) : null}
      </form>

      <div className="card p-2 sm:p-4">
        <EtfTable rows={rows} />
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-between text-xs text-muted">
          <span>
            第 {currentPage} / {totalPages} 页
          </span>
          <div className="flex gap-2">
            {currentPage > 1 ? (
              <Link
                href={pageHref(currentPage - 1)}
                className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink"
              >
                上一页
              </Link>
            ) : null}
            {currentPage < totalPages ? (
              <Link
                href={pageHref(currentPage + 1)}
                className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink"
              >
                下一页
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="grid gap-3 text-xs leading-6 text-muted sm:grid-cols-3">
        <p className="rounded-sm border border-line bg-surface p-4">
          <span className="font-medium text-ink">涨跌幅</span>
          <br />
          收盘价相对前收，使用复权价；分红除权日不会产生虚假下跌。
        </p>
        <p className="rounded-sm border border-line bg-surface p-4">
          <span className="font-medium text-ink">估值分位</span>
          <br />
          当前 PE 在近 5 年有效样本中的百分位；分位低不等于马上涨。
        </p>
        <p className="rounded-sm border border-line bg-surface p-4">
          <span className="font-medium text-ink">数据状态</span>
          <br />
          {live
            ? `来自本地数据管道，更新至 ${dataDate}；估值覆盖核心指数，其余显示 —。`
            : "Sprint 0 示例数据；启动 API 与数据管道后自动切换。"}
        </p>
      </div>
    </div>
  );
}
