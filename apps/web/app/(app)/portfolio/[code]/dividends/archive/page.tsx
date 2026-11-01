import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DividendArchiveTimeline } from "@/components/dividend-archive-timeline";
import { fetchStock } from "@/lib/stocks";

export const metadata: Metadata = {
  title: "个股分红档案",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";

function fmt(value: number | null, digits = 2): string {
  return value == null ? "—" : value.toFixed(digits);
}

export default async function DividendArchivePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  if (!/^\d{6}$/.test(code)) notFound();
  const stock = await fetchStock(code);
  if (!stock) {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm text-muted">分红档案暂时无法读取</p>
        <Link
          href={`/portfolio/${code}`}
          className="mt-4 inline-block text-sm text-jade-deep"
        >
          ← 返回持仓详情
        </Link>
      </div>
    );
  }

  const dividends = stock.dividends
    .filter((row) => row.cash_per_share > 0 && row.ex_date)
    .map((row) => ({ ...row, ex_date: row.ex_date as string }));
  const annual = new Map<number, number>();
  for (const row of dividends) {
    annual.set(row.fiscal_year, (annual.get(row.fiscal_year) ?? 0) + row.cash_per_share);
  }
  const years = [...annual.keys()].sort((a, b) => a - b);
  const latestYear = years.at(-1) ?? new Date().getFullYear();
  const firstYear = years[0] ?? latestYear;
  let continuous = 0;
  for (let year = latestYear; annual.has(year); year -= 1) continuous += 1;
  const span = Math.max(1, latestYear - firstYear + 1);
  const coverage = Math.min(100, Math.round((years.length / span) * 100));
  const base = annual.get(latestYear - 5);
  const latestCash = annual.get(latestYear) ?? 0;
  const growth =
    base && base > 0 && latestYear - 5 >= firstYear
      ? (Math.pow(latestCash / base, 1 / 5) - 1) * 100
      : null;
  const avg3 =
    [latestYear, latestYear - 1, latestYear - 2].reduce(
      (sum, year) => sum + (annual.get(year) ?? 0),
      0,
    ) / 3;
  const score = Math.max(
    0,
    Math.min(
      99,
      Math.round((continuous / span) * 65 + coverage * 0.2 + (growth != null && growth >= 0 ? 15 : 5)),
    ),
  );

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Link href={`/portfolio/${code}`} className="inline-block text-sm text-jade-deep">
        ← 返回持仓详情
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
            Dividend Archive
          </p>
          <h1 className="mt-1 font-serif text-2xl">个股分红档案</h1>
          <p className="mt-1 text-sm text-muted">
            {stock.code} {stock.name} · A股 · 人民币
          </p>
        </div>
        <Link
          href={`/stocks/${stock.code}?tab=dividend`}
          className="rounded-xl border border-line px-3 py-2 text-sm text-jade-deep"
        >
          公开分红详情
        </Link>
      </div>

      <div className="rounded-2xl border border-amber/30 bg-amber-soft/30 p-4 text-xs leading-6 text-ink-soft">
        <strong className="text-amber">风险提醒：</strong>
        本页数据基于公开历史分红整理，可能存在瑕疵或遗漏，仅供研究参考。
        历史表现不代表未来，不构成任何投资建议。
      </div>

      <section className="overflow-hidden rounded-2xl bg-ink text-paper">
        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-2xl font-semibold">{stock.name}</p>
              <p className="tnum mt-1 text-sm text-paper/60">{stock.code}</p>
            </div>
            <span className="rounded bg-amber px-2 py-1 text-xs">A股</span>
          </div>
          <p className="tnum mt-5 text-4xl font-semibold">
            ¥{fmt(stock.price)}
          </p>
          <p className="mt-1 text-xs text-paper/60">
            {stock.updated_at ? `${stock.updated_at.slice(0, 10)} 数据` : "最新收录行情"}
          </p>
        </div>
        <div className="grid grid-cols-3 divide-x divide-paper/15 border-t border-paper/15 py-4 text-center">
          <div>
            <p className="text-lg font-semibold text-amber">
              {stock.dividend_yield_ttm == null
                ? "—"
                : `${stock.dividend_yield_ttm.toFixed(2)}%`}
            </p>
            <p className="mt-1 text-xs text-paper/60">股息率 TTM</p>
          </div>
          <div>
            <p className="text-lg font-semibold">{continuous} 年</p>
            <p className="mt-1 text-xs text-paper/60">连续分红</p>
          </div>
          <div>
            <p className="text-lg font-semibold">{dividends.length} 次</p>
            <p className="mt-1 text-xs text-paper/60">累计分红</p>
          </div>
        </div>
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-medium">分红稳定性</h2>
            <p className="mt-1 text-xs text-muted">基于历史分红覆盖、连续性和增长综合评估</p>
          </div>
          <div className="flex h-16 w-16 items-center justify-center rounded-full border-4 border-amber/30 text-xl font-semibold text-amber">
            {score}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div className="rounded-xl bg-paper p-3">
            <p className="text-xs text-muted">连续分红</p>
            <p className="mt-1 font-medium">{continuous} 年</p>
          </div>
          <div className="rounded-xl bg-paper p-3">
            <p className="text-xs text-muted">近 5 年增长率</p>
            <p className="mt-1 font-medium">
              {growth == null ? "—" : `${growth >= 0 ? "+" : ""}${growth.toFixed(2)}%`}
            </p>
          </div>
          <div className="rounded-xl bg-paper p-3">
            <p className="text-xs text-muted">近 3 年均派息</p>
            <p className="mt-1 font-medium">¥{avg3.toFixed(2)}</p>
          </div>
          <div className="rounded-xl bg-paper p-3">
            <p className="text-xs text-muted">分红覆盖率</p>
            <p className="mt-1 font-medium">{coverage}%</p>
          </div>
        </div>
        <details className="mt-4 text-xs text-muted">
          <summary className="cursor-pointer text-jade-deep">这个分数怎么算？</summary>
          <p className="mt-2 leading-6">
            分数由连续分红年限、历年覆盖率、近 5 年每股分红变化综合计算，仅用于快速浏览历史稳定性。
            缺失年份按未覆盖处理，不推断为 0；预案和未实施记录不计入。
          </p>
        </details>
      </section>

      <DividendArchiveTimeline dividends={dividends} latestYear={latestYear} />
    </div>
  );
}
