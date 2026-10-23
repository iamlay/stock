import type { Metadata } from "next";

import { StockSectionTabs } from "@/components/stock-section-tabs";

export const metadata: Metadata = { title: "股息财务" };

export default function StockFinancialPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
          Financials
        </p>
        <h1 className="mt-1 font-serif text-3xl text-ink">股息财务</h1>
        <p className="mt-1 text-sm text-muted">
          年报 / 季报净利润、同比与披露日期
        </p>
      </div>

      <StockSectionTabs active="financial" />

      <div className="card p-10 text-center">
        <p className="text-sm text-ink">财务追踪正在开发中</p>
        <p className="mx-auto mt-2 max-w-lg text-xs leading-6 text-muted">
          需要新增财务数据表与 Eastmoney F10 同步任务，先覆盖高股息前 500
          只，再扩展到全市场。
        </p>
      </div>
    </div>
  );
}
