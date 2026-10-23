import type { Metadata } from "next";
import Link from "next/link";

import { StockSectionTabs } from "@/components/stock-section-tabs";
import { fetchIndustries } from "@/lib/api";

export const metadata: Metadata = {
  title: "申万一级行业",
  description:
    "按申万一级行业浏览 A 股，查看行业涨跌、样本数量，进入行业个股列表。",
  alternates: { canonical: "https://stock.iamlay.com/stocks/industry" },
};

export const dynamic = "force-dynamic";

export default async function StockIndustryIndexPage() {
  const industries = (await fetchIndustries()) ?? [];
  const sorted = [...industries].sort((a, b) => b.count - a.count);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
          Industries
        </p>
        <h1 className="mt-1 font-serif text-3xl text-ink">申万一级行业</h1>
        <p className="mt-1 text-sm text-muted">
          按行业浏览 A 股 · 行业涨跌为个股等权 · 数据来自申万一级分类
        </p>
      </div>

      <StockSectionTabs active="industry" />

      {sorted.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          行业数据暂不可用，请确认 API 已同步行业字段。
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((industry) => (
            <Link
              key={industry.name}
              href={`/stocks/industry/${encodeURIComponent(industry.name)}`}
              className="card flex items-center justify-between p-4 hover:border-jade/50"
            >
              <div>
                <p className="text-sm font-medium text-ink">{industry.name}</p>
                <p className="mt-1 text-xs text-muted">{industry.count} 只</p>
              </div>
              <span
                className={`tnum text-sm ${
                  industry.change_pct >= 0 ? "text-loss" : "text-jade"
                }`}
              >
                {industry.change_pct > 0 ? "+" : ""}
                {industry.change_pct.toFixed(2)}%
              </span>
            </Link>
          ))}
        </div>
      )}

      <p className="text-xs leading-6 text-muted">
        行业分类可能随数据源调整；行业涨跌是样本个股等权平均，不是官方行业指数。
      </p>
    </div>
  );
}
