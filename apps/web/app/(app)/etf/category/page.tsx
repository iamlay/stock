import type { Metadata } from "next";
import Link from "next/link";

import { fetchEtfs, toEtf } from "@/lib/api";
import { categories } from "@/lib/mock";

export const metadata: Metadata = {
  title: "ETF 分类",
  description: "按红利、现金流、跨境、宽基、行业、债券、商品、货币、策略浏览 ETF。",
  alternates: { canonical: "https://stock.iamlay.com/etf/category" },
};

export const dynamic = "force-dynamic";

export default async function EtfCategoryIndexPage() {
  const apiEtfs = await fetchEtfs();
  const rows = (apiEtfs ?? []).map(toEtf);
  const counts = new Map(categories.map((category) => [category, 0]));
  for (const row of rows) {
    counts.set(row.category, (counts.get(row.category) ?? 0) + 1);
  }

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1.5 text-xs text-muted">
        <Link href="/etf" className="hover:text-ink">ETF 数据</Link>
        <span>/</span>
        <span className="text-ink">分类</span>
      </nav>
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
          Categories
        </p>
        <h1 className="mt-1 font-serif text-3xl text-ink">ETF 分类</h1>
        <p className="mt-1 text-sm text-muted">按策略与资产类别浏览 ETF</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {categories.map((category) => (
          <Link
            key={category}
            href={`/etf/category/${encodeURIComponent(category)}`}
            className="card flex items-center justify-between p-4 hover:border-jade/50"
          >
            <span className="text-sm text-ink">{category}</span>
            <span className="tnum text-xs text-muted">{counts.get(category) ?? 0} 只</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
