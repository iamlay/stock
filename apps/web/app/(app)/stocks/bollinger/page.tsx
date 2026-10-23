import type { Metadata } from "next";

import { StockSectionTabs } from "@/components/stock-section-tabs";

export const metadata: Metadata = { title: "股息布林" };

export default function StockBollingerPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
          Bollinger Bands
        </p>
        <h1 className="mt-1 font-serif text-3xl text-ink">股息布林</h1>
        <p className="mt-1 text-sm text-muted">
          日 / 周 / 月布林位置与回踩评级 · 先覆盖高股息前 500 只
        </p>
      </div>

      <StockSectionTabs active="bollinger" />

      <div className="card p-10 text-center">
        <p className="text-sm text-ink">布林追踪正在开发中</p>
        <p className="mx-auto mt-2 max-w-lg text-xs leading-6 text-muted">
          需要基于个股日线、周线、月线计算 20 周期均线与标准差。当前 K 线覆盖高股息前
          500 只，上线后先展示这 500 只，再逐步扩展。
        </p>
      </div>
    </div>
  );
}
