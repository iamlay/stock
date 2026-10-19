import type { Metadata } from "next";
import Link from "next/link";

import { EtfTable } from "@/components/etf-table";
import { fetchEtfs, fetchOverview, toEtf } from "@/lib/api";
import { etfs, sectors, strategies } from "@/lib/mock";
import { fmtPct, trendBg, trendClass } from "@/lib/format";

export const metadata: Metadata = { title: "今日市场" };
export const revalidate = 60;

const fallbackStats = [
  { label: "沪深 300", value: "4,018.55", hint: "较上一交易日" },
  { label: "两市成交", value: "1.87 万亿", hint: "较 5 日均值" },
  { label: "涨跌家数", value: "3,124 / 1,893", hint: "上涨 / 下跌" },
  { label: "股债利差", value: "5.42%", hint: "近 5 年 72% 分位" },
];

export default async function DashboardPage() {
  const [apiEtfs, overview] = await Promise.all([fetchEtfs(), fetchOverview()]);
  const live = Boolean(apiEtfs?.length && overview && !overview.demo);
  const list = apiEtfs && apiEtfs.length > 0 ? apiEtfs.map(toEtf) : etfs;
  const top = [...list].sort((a, b) => (b.aum ?? 0) - (a.aum ?? 0)).slice(0, 8);

  const drawdowns = list
    .map((etf) => etf.maxDrawdown)
    .filter((value): value is number => typeof value === "number");
  const avgDrawdown = drawdowns.length
    ? drawdowns.reduce((sum, value) => sum + value, 0) / drawdowns.length
    : 0;

  const stats =
    live && overview
      ? [
          {
            label: "重点 ETF 等权",
            value: fmtPct(overview.avg_change_pct ?? 0),
            hint: `${overview.etf_count} 只等权`,
          },
          {
            label: "成交额",
            value: `${(overview.turnover_billion ?? 0).toFixed(0)} 亿`,
            hint: "重点 ETF 合计",
          },
          {
            label: "涨跌家数",
            value: `${overview.advancing} / ${overview.declining}`,
            hint: "上涨 / 下跌",
          },
          {
            label: "平均回撤",
            value: `${avgDrawdown.toFixed(1)}%`,
            hint: "近 1 年 · 等权",
          },
        ]
      : fallbackStats;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">今日市场</h1>
          <p className="mt-1 text-sm text-muted">
            {overview?.trade_date ?? "2026-10-19"} 收盘 · {live ? "真实数据" : "示例数据"}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="rounded-sm border border-line bg-surface px-2.5 py-1">日频</span>
          <span className="rounded-sm border border-line bg-surface px-2.5 py-1">18:30 更新</span>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="card p-4">
            <p className="text-xs text-muted">{stat.label}</p>
            <p className="tnum mt-2 text-xl font-semibold text-ink">{stat.value}</p>
            <p className="tnum mt-1 text-xs text-muted">{stat.hint}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-medium text-ink">板块热力</h2>
              <p className="mt-0.5 text-xs text-muted">申万一级行业 · 当日涨跌幅（示例）</p>
            </div>
            <span className="text-xs text-muted">红涨绿跌</span>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4">
            {sectors.map((sector) => (
              <div
                key={sector.name}
                className="flex h-20 flex-col justify-between rounded-sm border border-line/60 p-2.5"
                style={{ backgroundColor: trendBg(sector.change) }}
              >
                <span className="text-xs text-ink">{sector.name}</span>
                <span className={`tnum text-sm font-medium ${trendClass(sector.change)}`}>
                  {fmtPct(sector.change)}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">
            颜色越深表示涨跌幅越大；示例数据，接入申万行业日线后替换。
          </p>
        </section>

        <section className="space-y-4">
          <div className="card p-5">
            <h2 className="text-base font-medium text-ink">市场温度</h2>
            <div className="mt-4 flex items-end justify-between">
              <p className="tnum text-4xl font-semibold text-ink">
                62<span className="ml-1 text-sm font-normal text-muted">/ 100</span>
              </p>
              <span className="rounded-sm bg-amber-soft px-2 py-1 text-[11px] text-amber">偏暖</span>
            </div>
            <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-line">
              <div className="h-full w-[62%] rounded-full bg-gradient-to-r from-jade to-amber" />
            </div>
            <p className="mt-3 text-xs leading-5 text-muted">
              综合成交额、涨跌分布、涨停家数与估值分位。温度高不代表该追，只代表情绪偏热。
            </p>
          </div>

          <div className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-medium text-ink">策略速览</h2>
              <Link href="/strategies" className="text-xs text-jade-deep hover:underline">
                全部 →
              </Link>
            </div>
            <ul className="mt-3 divide-y divide-line">
              {strategies.slice(1).map((strategy) => (
                <li key={strategy.slug} className="flex items-center justify-between py-2.5">
                  <div>
                    <p className="text-sm text-ink">{strategy.name}</p>
                    <p className="text-[11px] text-muted">
                      回撤 {strategy.maxDrawdown.toFixed(1)}%
                    </p>
                  </div>
                  <span className="tnum text-sm font-medium text-loss">
                    +{strategy.totalReturn.toFixed(1)}%
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="card p-5">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-base font-medium text-ink">重点 ETF</h2>
            <p className="mt-0.5 text-xs text-muted">
              按规模排序 · {live ? `更新至 ${overview?.trade_date}` : "示例数据"}
            </p>
          </div>
          <Link href="/etf" className="text-xs text-jade-deep hover:underline">
            查看全部 →
          </Link>
        </div>
        <div className="mt-4">
          <EtfTable rows={top} compact />
        </div>
      </section>

      <section className="rounded-sm border border-amber/20 bg-amber-soft/60 p-4 text-xs leading-6 text-amber">
        {live
          ? `行情与规模来自本地数据管道，更新至 ${overview?.trade_date}；板块热力与策略速览仍为示例。`
          : "当前为示例数据：启动 API、执行 W2 数据同步后，本页会自动切换到真实行情。"}
      </section>
    </div>
  );
}
