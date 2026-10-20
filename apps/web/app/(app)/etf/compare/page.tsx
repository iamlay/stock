import type { Metadata } from "next";
import Link from "next/link";

import { CompareChart } from "@/components/compare-chart";
import { ComparePicker } from "@/components/compare-picker";
import { fetchCompare, fetchEtfs } from "@/lib/api";
import { fmtPct, trendClass } from "@/lib/format";
import { etfs } from "@/lib/mock";

export const metadata: Metadata = { title: "ETF 对比" };
export const revalidate = 60;

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ codes?: string; days?: string }>;
}) {
  const params = await searchParams;
  const apiEtfs = await fetchEtfs();
  const options =
    apiEtfs?.map((item) => ({ code: item.code, name: item.name })) ??
    etfs.map((item) => ({ code: item.code, name: item.name }));

  const requested = (params.codes ?? "")
    .split(",")
    .map((code) => code.trim())
    .filter((code) => options.some((option) => option.code === code));
  const selected =
    requested.length >= 2
      ? requested.slice(0, 5)
      : options.slice(0, 3).map((option) => option.code);
  const days = [60, 120, 250, 500].includes(Number(params.days))
    ? Number(params.days)
    : 250;

  const data = selected.length >= 2 ? await fetchCompare(selected, days) : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <nav className="text-xs text-muted">
            <Link href="/etf" className="hover:text-ink">
              ETF 数据
            </Link>
            <span className="mx-1.5">/</span>
            <span className="text-ink">对比</span>
          </nav>
          <h1 className="mt-2 font-serif text-3xl text-ink">ETF 对比</h1>
          <p className="mt-1 text-sm text-muted">
            同一时间窗口归一化到 100，比较收益、回撤与波动
          </p>
        </div>
        <Link
          href="/watchlist"
          className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
        >
          从自选添加
        </Link>
      </div>

      <ComparePicker options={options} selected={selected} days={days} />

      {data ? (
        <>
          <section className="card p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-base font-medium text-ink">归一化走势</h2>
              <p className="text-xs text-muted">
                {data.start} 至 {data.end} · {data.days} 个交易日
              </p>
            </div>
            <div className="mt-4">
              <CompareChart items={data.items} />
            </div>
          </section>

          <section className="card p-5">
            <h2 className="text-base font-medium text-ink">区间指标</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="py-2 pr-3 font-medium">名称</th>
                    <th className="py-2 pr-3 font-medium">分类</th>
                    <th className="py-2 pr-3 text-right font-medium">累计收益</th>
                    <th className="py-2 pr-3 text-right font-medium">最大回撤</th>
                    <th className="py-2 pr-3 text-right font-medium">年化波动</th>
                    <th className="py-2 text-right font-medium">详情</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <tr key={item.code} className="border-b border-line/60">
                      <td className="py-2 pr-3">
                        <span className="font-medium text-ink">{item.name}</span>
                        <span className="ml-2 tnum text-[11px] text-muted">{item.code}</span>
                      </td>
                      <td className="py-2 pr-3 text-xs text-ink-soft">{item.category}</td>
                      <td className={`tnum py-2 pr-3 text-right ${trendClass(item.total_return)}`}>
                        {fmtPct(item.total_return)}
                      </td>
                      <td className="tnum py-2 pr-3 text-right text-loss">
                        {item.max_drawdown.toFixed(2)}%
                      </td>
                      <td className="tnum py-2 pr-3 text-right text-ink-soft">
                        {item.volatility.toFixed(2)}%
                      </td>
                      <td className="py-2 text-right">
                        <Link
                          href={`/etf/${item.code}`}
                          className="text-xs text-jade-deep hover:underline"
                        >
                          查看
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : (
        <section className="card p-8 text-center">
          <p className="text-sm text-muted">
            API 不可用，或所选 ETF 没有足够的共同交易日数据。
          </p>
          <p className="mt-2 text-xs text-muted">
            请确认已启动 API、执行 ETL，并至少选择 2 只有行情的 ETF。
          </p>
        </section>
      )}
    </div>
  );
}
