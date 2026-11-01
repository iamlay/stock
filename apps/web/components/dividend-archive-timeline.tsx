"use client";

import { useMemo, useState } from "react";

type Dividend = {
  ex_date: string | null;
  fiscal_year: number;
  cash_per_share: number;
  plan: string;
};

const RANGES = [
  ["1", "1年"],
  ["3", "3年"],
  ["5", "5年"],
  ["all", "全部"],
] as const;

export function DividendArchiveTimeline({
  dividends,
  latestYear,
}: {
  dividends: Dividend[];
  latestYear: number;
}) {
  const [range, setRange] = useState<(typeof RANGES)[number][0]>("3");
  const rows = useMemo(() => {
    const sorted = [...dividends].sort((a, b) =>
      (b.ex_date ?? "").localeCompare(a.ex_date ?? ""),
    );
    if (range === "all") return sorted;
    const years = Number(range);
    return sorted.filter((row) => row.fiscal_year > latestYear - years);
  }, [dividends, latestYear, range]);

  return (
    <section className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <h2 className="font-medium">历史分红</h2>
        <div className="flex flex-wrap gap-1">
          {RANGES.map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setRange(value)}
              className={`rounded-full px-3 py-1.5 text-xs ${
                range === value ? "bg-ink text-paper" : "bg-paper text-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {rows.length ? (
        <div className="divide-y divide-line/60">
          {rows.map((row, index) => (
            <div
              key={`${row.ex_date}-${row.fiscal_year}-${index}`}
              className="flex items-center justify-between gap-3 px-5 py-4"
            >
              <div>
                <p className="tnum text-sm font-medium">{row.ex_date ?? "日期待核对"}</p>
                <p className="mt-1 text-xs text-muted">{row.plan || "分红方案待核对"}</p>
              </div>
              <div className="text-right">
                <p className="tnum text-sm text-ink">
                  ¥{row.cash_per_share.toFixed(4)}
                </p>
                <p className="text-xs text-muted">每股现金</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="p-6 text-sm text-muted">该时间范围内没有已收录的分红记录。</p>
      )}
    </section>
  );
}
