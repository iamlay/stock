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
    if (row.is_special) continue;
    annual.set(row.fiscal_year, (annual.get(row.fiscal_year) ?? 0) + row.cash_per_share);
  }
  const years = [...annual.keys()].sort((a, b) => a - b);
  const latestYear = years.at(-1) ?? new Date().getFullYear();
  const currentYear = new Date().getFullYear();
  // The current fiscal year is incomplete and must not lower continuity/coverage.
  const completedYears = years.filter((year) => year < currentYear);
  const scoredYears = completedYears.length ? completedYears : years;
  const latestCompleted = scoredYears.at(-1) ?? latestYear;
  const firstYear = scoredYears[0] ?? latestCompleted;
  const span = Math.max(1, latestCompleted - firstYear + 1);
  const ageBase = Math.min(10, span);

  let continuous = 0;
  for (let year = latestCompleted; annual.has(year); year -= 1) continuous += 1;
  const continuityScore = 30 * Math.min(1, continuous / ageBase);

  const series: number[] = [];
  for (let year = firstYear; year <= latestCompleted; year += 1) {
    series.push(annual.get(year) ?? 0);
  }
  const changes: number[] = [];
  for (let index = 1; index < series.length; index += 1) {
    const previous = series[index - 1];
    const current = series[index];
    if (previous > 0) changes.push(Math.abs(current / previous - 1));
    else if (current > 0) changes.push(1);
  }
  const maxChange = changes.length ? Math.max(...changes) : 0;
  const stabilityScore = 30 * Math.max(0, Math.min(1, 1 - Math.max(0, maxChange - 0.5) / 0.5));

  const baseYear = Math.max(firstYear, latestCompleted - 5);
  const baseCash = annual.get(baseYear) ?? 0;
  const latestCash = annual.get(latestCompleted) ?? 0;
  const growthYears = latestCompleted - baseYear;
  const growth =
    baseCash > 0 && latestCash > 0 && growthYears > 0
      ? (Math.pow(latestCash / baseCash, 1 / growthYears) - 1) * 100
      : null;
  const growthScore =
    20 * Math.max(0, Math.min(1, ((growth ?? -5) + 5) / 13));

  const coveredYears = series.filter((value) => value > 0).length;
  const coverage = Math.round((coveredYears / span) * 100);
  const coverageScore = 20 * Math.min(1, coveredYears / span);
  const avg3 =
    [latestCompleted, latestCompleted - 1, latestCompleted - 2].reduce(
      (sum, year) => sum + (annual.get(year) ?? 0),
      0,
    ) / 3;
  const breakdown = [
    {
      label: "连续性",
      score: Math.round(continuityScore),
      max: 30,
      note: `从 ${latestCompleted} 年往回连续 ${continuous} 年；按 ${ageBase} 年满分基准计算。`,
    },
    {
      label: "稳定性",
      score: Math.round(stabilityScore),
      max: 30,
      note: `年度派息最大变动 ${(maxChange * 100).toFixed(1)}%；稳步增长不扣分，剧烈波动扣分。`,
    },
    {
      label: "增长趋势",
      score: Math.round(growthScore),
      max: 20,
      note:
        growth == null
          ? "历史不足，暂不计算增长分。"
          : `近 ${growthYears} 年每股分红年均 ${growth >= 0 ? "+" : ""}${growth.toFixed(2)}%；8% 以上满分。`,
    },
    {
      label: "分红覆盖",
      score: Math.round(coverageScore),
      max: 20,
      note: `${firstYear}–${latestCompleted} 共 ${span} 年，有 ${coveredYears} 年分红，覆盖率 ${coverage}%。`,
    },
  ];
  const score = Math.max(
    0,
    Math.min(
      100,
      Math.round(breakdown.reduce((sum, item) => sum + item.score, 0)),
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
        <details open className="mt-4 text-xs text-muted">
          <summary className="cursor-pointer text-jade-deep">这个分数怎么算？</summary>
          <div className="mt-3 space-y-3">
            {breakdown.map((item) => (
              <div key={item.label} className="rounded-xl bg-paper p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-ink-soft">{item.label}</p>
                  <p className="tnum text-jade-deep">
                    {item.score} / {item.max}
                  </p>
                </div>
                <p className="mt-1 leading-6">{item.note}</p>
              </div>
            ))}
            <p className="leading-6">
              总分 {score} / 100。当年数据不完整，不参与评分；预案和未实施记录不计入。
              缺失年份按未覆盖处理，不推断为 0。评分仅供参考，不构成投资建议。
            </p>
          </div>
        </details>
      </section>

      <DividendArchiveTimeline dividends={dividends} latestYear={latestYear} />
    </div>
  );
}
