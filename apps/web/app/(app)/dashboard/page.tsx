import type { Metadata } from "next";
import Link from "next/link";

import { EtfTable } from "@/components/etf-table";
import { CategoryHeatChart } from "@/components/category-heat-chart";
import { fetchEtfs, fetchOverview, fetchStrategySummaries, toEtf } from "@/lib/api";
import { etfs, strategies } from "@/lib/mock";
import { fmtPct } from "@/lib/format";

export const metadata: Metadata = { title: "今日市场" };
export const revalidate = 60;

const fallbackStats = [
  { label: "沪深 300", value: "4,018.55", hint: "较上一交易日" },
  { label: "两市成交", value: "1.87 万亿", hint: "较 5 日均值" },
  { label: "涨跌家数", value: "3,124 / 1,893", hint: "上涨 / 下跌" },
  { label: "股债利差", value: "5.42%", hint: "近 5 年 72% 分位" },
];

export default async function DashboardPage() {
  const [apiEtfs, overview, strategySummary] = await Promise.all([
    fetchEtfs(),
    fetchOverview(),
    fetchStrategySummaries("510300"),
  ]);
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
            value: `${Number(avgDrawdown).toFixed(1)}%`,
            hint: "近 1 年 · 等权",
          },
        ]
      : fallbackStats;

  const categoryMap = new Map<string, { sum: number; count: number }>();
  for (const etf of list) {
    const current = categoryMap.get(etf.category) ?? { sum: 0, count: 0 };
    current.sum += etf.change;
    current.count += 1;
    categoryMap.set(etf.category, current);
  }
  const heat = Array.from(categoryMap.entries())
    .map(([name, value]) => ({
      name,
      change: value.sum / value.count,
      count: value.count,
    }))
    .sort((a, b) => b.change - a.change);

  const breadth =
    overview && overview.advancing + overview.declining > 0
      ? overview.advancing / (overview.advancing + overview.declining)
      : 0.5;
  const temperature = overview
    ? Math.max(
        0,
        Math.min(
          100,
          Math.round(50 + (overview.avg_change_pct ?? 0) * 8 + (breadth - 0.5) * 40),
        ),
      )
    : 50;
  const temperatureLabel =
    temperature >= 70
      ? "偏热"
      : temperature >= 55
        ? "偏暖"
        : temperature >= 45
          ? "中性"
          : temperature >= 30
            ? "偏冷"
            : "寒冷";

  const quickStrategies =
    strategySummary?.items.slice(0, 5).map((item) => ({
      slug: item.slug,
      name: item.name,
      totalReturn: item.total_return,
      maxDrawdown: item.max_drawdown,
    })) ??
    strategies.slice(1, 6).map((item) => ({
      slug: item.slug,
      name: item.name,
      totalReturn: item.totalReturn,
      maxDrawdown: item.maxDrawdown,
    }));

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">今日市场</h1>
          <p className="mt-1 text-sm text-muted">
            {overview?.quote_time
              ? `最新报价 ${overview.quote_time.slice(11, 16)}`
              : `${overview?.trade_date ?? "2026-10-19"} 收盘`}{" "}
            · {live ? "真实数据" : "示例数据"}
          </p>
        </div>
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="rounded-sm border border-line bg-surface px-2.5 py-1">日频</span>
            <span className="rounded-sm border border-line bg-surface px-2.5 py-1">
              {overview?.quote_time
                ? `更新 ${overview.quote_time.slice(11, 16)}`
                : "18:30 更新"}
            </span>
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
              <h2 className="text-base font-medium text-ink">ETF 分类涨跌</h2>
              <p className="mt-0.5 text-xs text-muted">
                重点 ETF 按分类等权 · 当日涨跌幅
              </p>
            </div>
            <span className="text-xs text-muted">红涨绿跌</span>
          </div>
          <CategoryHeatChart data={heat} />
          <p className="mt-3 text-xs text-muted">
            {live
              ? `基于 ${list.length} 只重点 ETF 分类等权，非申万全行业。`
              : "当前为示例数据；API 连通后自动切换为真实 ETF 分类涨跌。"}
          </p>
        </section>

        <section className="space-y-4">
          <div className="card p-5">
            <h2 className="text-base font-medium text-ink">市场温度</h2>
            <div className="mt-4 flex items-end justify-between">
              <p className="tnum text-4xl font-semibold text-ink">
                {temperature}
                <span className="ml-1 text-sm font-normal text-muted">/ 100</span>
              </p>
              <span className="rounded-sm bg-amber-soft px-2 py-1 text-[11px] text-amber">
                {temperatureLabel}
              </span>
            </div>
            <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-gradient-to-r from-jade to-amber"
                style={{ width: `${temperature}%` }}
              />
            </div>
            <p className="mt-3 text-xs leading-5 text-muted">
              基于重点 ETF 等权涨跌与涨跌家数估算，非全市场温度。温度高不代表该追，只代表情绪偏热。
            </p>
          </div>

          <div className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-medium text-ink">策略速览</h2>
              <div className="flex items-center gap-2">
                {strategySummary ? null : (
                  <span className="rounded-sm bg-[#f1efe8] px-1.5 py-0.5 text-[10px] text-ink-soft">
                    示例
                  </span>
                )}
                <Link href="/strategies" className="text-xs text-jade-deep hover:underline">
                  全部 →
                </Link>
              </div>
            </div>
            <ul className="mt-3 divide-y divide-line">
              {quickStrategies.map((strategy) => (
                <li key={strategy.slug} className="flex items-center justify-between py-2.5">
                  <div>
                    <p className="text-sm text-ink">{strategy.name}</p>
                    <p className="text-[11px] text-muted">
                      回撤 {strategy.maxDrawdown.toFixed(1)}%
                    </p>
                  </div>
                  <span
                    className={`tnum text-sm font-medium ${
                      strategy.totalReturn >= 0 ? "text-gain" : "text-loss"
                    }`}
                  >
                    {strategy.totalReturn >= 0 ? "+" : ""}
                    {strategy.totalReturn.toFixed(1)}%
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
          ? `行情与规模来自本地数据管道，更新至 ${overview?.trade_date}；分类热力基于重点 ETF，市场温度为估算${
              strategySummary ? "，策略速览为真实回测" : "，策略速览暂为示例"
            }。`
          : "当前为示例数据：检查 Web 服务的 API_BASE_URL 是否指向 Railway API。"}
      </section>
    </div>
  );
}
