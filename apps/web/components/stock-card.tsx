import Link from "next/link";

import type { Stock } from "@/lib/stocks";
import { fmtPct, trendClass } from "@/lib/format";

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

export function SustainBadge({ value }: { value: string | null }) {
  if (!value || !SUSTAIN[value]) return null;
  const item = SUSTAIN[value];
  return (
    <span
      title={item.title}
      className={`inline-block rounded-sm px-1.5 py-0.5 text-[10px] ${item.className}`}
    >
      {item.label}
    </span>
  );
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

export function StockCard({ stock }: { stock: Stock }) {
  return (
    <Link
      href={`/stocks/${stock.code}`}
      className="block border-b border-line/70 p-4 last:border-0 hover:bg-black/[0.02]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[15px] font-medium text-ink">
            {stock.name}
            {stock.is_st ? (
              <span className="ml-2 rounded-sm bg-loss/10 px-1.5 py-0.5 text-[10px] text-loss">
                ST
              </span>
            ) : null}
          </p>
          <p className="tnum mt-0.5 text-[11px] text-muted">
            {stock.code} · {stock.industry ?? "未分类"}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="tnum text-lg font-semibold text-jade-deep">
            {pct(stock.dividend_yield_ttm)}
          </p>
          <p className="text-[10px] text-muted">股息率 TTM</p>
        </div>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="tnum text-sm text-ink">
            {stock.price == null ? "—" : stock.price.toFixed(2)}
          </span>
          <span
            className={`tnum text-xs ${
              stock.change_pct == null ? "text-muted" : trendClass(stock.change_pct)
            }`}
          >
            {stock.change_pct == null ? "—" : fmtPct(stock.change_pct)}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted">
          <span>
            市值 {stock.market_cap == null ? "—" : `${stock.market_cap.toFixed(0)} 亿`}
          </span>
          <SustainBadge value={stock.sustainability} />
        </div>
      </div>
    </Link>
  );
}
