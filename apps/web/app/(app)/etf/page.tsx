import type { Metadata } from "next";
import Link from "next/link";

import { EtfTable } from "@/components/etf-table";
import { categories, etfs, type EtfCategory } from "@/lib/mock";

export const metadata: Metadata = { title: "ETF 数据" };

export default async function EtfListPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const { category } = await searchParams;
  const active = categories.includes(category as EtfCategory) ? (category as EtfCategory) : null;
  const rows = active ? etfs.filter((etf) => etf.category === active) : etfs;
  const totalAum = rows.reduce((sum, etf) => sum + etf.aum, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">ETF 数据</h1>
          <p className="mt-1 text-sm text-muted">20 只重点标的 · 红利 / 现金流 / 跨境 / 宽基 / 行业</p>
        </div>
        <p className="tnum text-xs text-muted">
          {rows.length} 只 · 合计规模 {totalAum.toFixed(0)} 亿（示例）
        </p>
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
          Sprint 0 为示例数据；W2–W3 接入日线、份额与估值后替换。
        </p>
      </div>
    </div>
  );
}
