import Link from "next/link";

import type { Etf } from "@/lib/mock";
import { fmtNumber, fmtPct, trendClass } from "@/lib/format";

const categoryStyles: Record<string, string> = {
  红利: "bg-jade-soft text-jade-deep",
  现金流: "bg-amber-soft text-amber",
  跨境: "bg-[#eef1f8] text-[#3d4f7c]",
  宽基: "bg-[#f1efe8] text-ink-soft",
  行业: "bg-[#f8ece9] text-[#9a3f2c]",
};

export function EtfTable({ rows, compact = false }: { rows: Etf[]; compact?: boolean }) {
  const showPercentile = rows.some((etf) => etf.pePercentile !== null);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs font-medium text-muted">
            <th className="py-2.5 pr-3 font-medium">代码 / 名称</th>
            <th className="hidden px-3 py-2.5 font-medium sm:table-cell">分类</th>
            <th className="px-3 py-2.5 text-right font-medium">最新价</th>
            <th className="px-3 py-2.5 text-right font-medium">日涨跌</th>
            <th className="hidden px-3 py-2.5 text-right font-medium sm:table-cell">规模（亿）</th>
            <th className="hidden px-3 py-2.5 text-right font-medium md:table-cell">股息率</th>
            <th className="hidden px-3 py-2.5 text-right font-medium md:table-cell">
              {showPercentile ? "估值分位" : "MA20"}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((etf) => (
            <tr key={etf.code} className="group border-b border-line/70 last:border-0">
              <td className="py-3 pr-3">
                <Link href={`/etf/${etf.code}`} className="block">
                  <span className="tnum text-xs text-muted">{etf.code}</span>
                  <span className="ml-2 text-[13px] font-medium text-ink group-hover:text-jade-deep">
                    {etf.name}
                  </span>
                </Link>
              </td>
              <td className="hidden px-3 py-3 sm:table-cell">
                <span
                  className={`inline-flex rounded-sm px-1.5 py-0.5 text-[11px] ${categoryStyles[etf.category] ?? "bg-black/5 text-ink-soft"}`}
                >
                  {etf.category}
                </span>
              </td>
              <td className="tnum px-3 py-3 text-right text-ink">{fmtNumber(etf.price, 3)}</td>
              <td className={`tnum px-3 py-3 text-right ${trendClass(etf.change)}`}>
                {fmtPct(etf.change)}
              </td>
              <td className="tnum hidden px-3 py-3 text-right text-ink-soft sm:table-cell">
                {etf.aum === null ? "—" : fmtNumber(etf.aum, 1)}
              </td>
              <td className="tnum hidden px-3 py-3 text-right text-ink-soft md:table-cell">
                {etf.dividendYield === null ? "—" : `${etf.dividendYield.toFixed(1)}%`}
              </td>
              <td className="hidden px-3 py-3 text-right md:table-cell">
                {showPercentile ? (
                  etf.pePercentile === null ? (
                    <span className="text-xs text-muted">—</span>
                  ) : (
                    <div className="flex items-center justify-end gap-2">
                      <span className="h-1 w-14 overflow-hidden rounded-full bg-line">
                        <span
                          className="block h-full rounded-full bg-jade/70"
                          style={{ width: `${Math.min(etf.pePercentile, 100)}%` }}
                        />
                      </span>
                      <span className="tnum w-8 text-right text-xs text-muted">
                        {etf.pePercentile}%
                      </span>
                    </div>
                  )
                ) : (
                  <span className="tnum text-ink-soft">
                    {etf.ma20 == null ? "—" : fmtNumber(etf.ma20, 3)}
                  </span>
                )}
              </td>
              {!compact ? <td className="w-6" /> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
