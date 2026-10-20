import type { Metadata } from "next";
import Link from "next/link";

import { EquityCurve } from "@/components/equity-curve";
import { fetchStrategySummaries } from "@/lib/api";
import { strategies } from "@/lib/mock";

export const metadata: Metadata = { title: "策略实验室" };
export const dynamic = "force-dynamic";

type StrategyCard = {
  slug: string;
  name: string;
  summary: string;
  tag: string;
  curve: number[];
  totalReturn: number;
  annual: number;
  maxDrawdown: number;
  sharpe: number;
  benchmarkReturn?: number;
};

export default async function StrategiesPage() {
  const summary = await fetchStrategySummaries("510300");
  const live = Boolean(summary && summary.items.length > 0);
  const cards: StrategyCard[] = live
    ? summary!.items.map((item) => ({
        slug: item.slug,
        name: item.name,
        summary: item.description,
        tag: "实测",
        curve: item.curve,
        totalReturn: item.total_return,
        annual: item.annualized_return,
        maxDrawdown: item.max_drawdown,
        sharpe: item.sharpe,
        benchmarkReturn: item.benchmark_return,
      }))
    : strategies.map((strategy) => ({
        slug: strategy.slug,
        name: strategy.name,
        summary: strategy.summary,
        tag: strategy.tag,
        curve: strategy.curve,
        totalReturn: strategy.totalReturn,
        annual: strategy.annual,
        maxDrawdown: strategy.maxDrawdown,
        sharpe: strategy.sharpe,
      }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">策略实验室</h1>
          <p className="mt-1 text-sm text-muted">
            8 个规则策略 · 参数可调 · T+1 撮合
            {live
              ? ` · 当前基于 ${summary!.name}（${summary!.code}）实测`
              : " · API 未连接，暂显示示例指标"}
          </p>
        </div>
        <span className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-muted">
          {live ? `${summary!.start} 至 ${summary!.end}` : "历史回测 · 非实盘建议"}
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {cards.map((strategy) => (
          <Link
            key={strategy.slug}
            href={`/strategies/${strategy.slug}`}
            className="card group p-5 transition-colors hover:border-jade/50"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-medium text-ink group-hover:text-jade-deep">
                    {strategy.name}
                  </h2>
                  <span
                    className={`rounded-sm px-2 py-0.5 text-[11px] ${
                      strategy.tag === "实测"
                        ? "bg-jade-soft text-jade-deep"
                        : "bg-[#f1efe8] text-ink-soft"
                    }`}
                  >
                    {strategy.tag}
                  </span>
                </div>
                <p className="mt-2 max-w-md text-xs leading-5 text-muted">{strategy.summary}</p>
              </div>
              <span className="text-muted">→</span>
            </div>

            <div className="mt-4">
              <EquityCurve id={`strategy-${strategy.slug}`} points={strategy.curve} height={140} />
            </div>

            <dl className="mt-4 grid grid-cols-4 gap-2 border-t border-line pt-3 text-xs">
              <div>
                <dt className="text-muted">累计</dt>
                <dd
                  className={`tnum mt-1 font-medium ${
                    strategy.totalReturn >= 0 ? "text-gain" : "text-loss"
                  }`}
                >
                  {strategy.totalReturn >= 0 ? "+" : ""}
                  {strategy.totalReturn.toFixed(1)}%
                </dd>
              </div>
              <div>
                <dt className="text-muted">年化</dt>
                <dd className="tnum mt-1 font-medium text-ink">{strategy.annual.toFixed(1)}%</dd>
              </div>
              <div>
                <dt className="text-muted">最大回撤</dt>
                <dd className="tnum mt-1 font-medium text-jade">
                  {strategy.maxDrawdown.toFixed(1)}%
                </dd>
              </div>
              <div>
                <dt className="text-muted">夏普</dt>
                <dd className="tnum mt-1 font-medium text-ink">{strategy.sharpe.toFixed(2)}</dd>
              </div>
            </dl>
            {strategy.benchmarkReturn !== undefined ? (
              <p className="mt-2 text-[11px] text-muted">
                同期基准：{strategy.benchmarkReturn >= 0 ? "+" : ""}
                {strategy.benchmarkReturn.toFixed(1)}%
              </p>
            ) : null}
          </Link>
        ))}
      </div>

      <div className="rounded-sm border border-line bg-surface p-5 text-sm leading-6 text-ink-soft">
        <p className="font-medium text-ink">回测口径</p>
        <p className="mt-2 text-xs leading-6 text-muted">
          信号在 T 日收盘后计算，默认 T+1 开盘成交；佣金 0.02%（最低 5 元）、滑点 2bp；停牌不成交，开盘涨跌停不成交；分红再投，后复权计算。所有策略页均展示完整成交假设。
        </p>
      </div>
    </div>
  );
}
