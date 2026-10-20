import type { Metadata } from "next";
import Link from "next/link";

import { EtfTable } from "@/components/etf-table";
import { fetchEtfs, toEtf } from "@/lib/api";
import { categories, etfs, type EtfCategory } from "@/lib/mock";

export const metadata: Metadata = { title: "ETF 数据" };
export const revalidate = 60;

export default async function EtfListPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const { category } = await searchParams;
  const active = categories.includes(category as EtfCategory) ? (category as EtfCategory) : null;

  const apiEtfs = await fetchEtfs();
  const live = Boolean(apiEtfs && apiEtfs.length > 0);
  const all = apiEtfs && apiEtfs.length > 0 ? apiEtfs.map(toEtf) : etfs;
  const rows = active ? all.filter((etf) => etf.category === active) : all;
  const totalAum = rows.reduce((sum, etf) => sum + (etf.aum ?? 0), 0);
  const dataDate = apiEtfs?.[0]?.trade_date ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">ETF 数据</h1>
          <p className="mt-1 text-sm text-muted">20 只重点标的 · 红利 / 现金流 / 跨境 / 宽基 / 行业</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/etf/compare"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            对比
          </Link>
          <p className="tnum text-xs text-muted">
            {rows.length} 只 · 合计规模 {totalAum.toFixed(0)} 亿 · {live ? `数据 ${dataDate}` : "示例数据"}
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
          全部
        </Link>
        {categories.map((item) => (
          <Link
            key={item}
            href={`/etf?category=${encodeURIComponent(item)}`}
            className={`rounded-sm border px-3 py-1.5 text-xs transition-colors ${
              active === item
                ? "border-ink bg-ink text-paper"
                : "border-line bg-surface text-ink-soft hover:border-ink"
            }`}
          >
            {item}
          </Link>
        ))}
      </div>

      <div className="card p-2 sm:p-4">
        <EtfTable rows={rows} />
      </div>

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
