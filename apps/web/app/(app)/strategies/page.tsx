import type { Metadata } from "next";
import Link from "next/link";

import { EquityCurve } from "@/components/equity-curve";
import { strategies } from "@/lib/mock";

export const metadata: Metadata = { title: "策略实验室" };

export default function StrategiesPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">策略实验室</h1>
          <p className="mt-1 text-sm text-muted">9 个规则策略 · 参数可改 · 成交可查（当前展示 4 个示例）</p>
        </div>
        <span className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-muted">
          历史回测 · 非实盘建议
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {strategies.map((strategy) => (
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
                  <span className="rounded-sm bg-jade-soft px-2 py-0.5 text-[11px] text-jade-deep">
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
                <dd className="tnum mt-1 font-medium text-loss">+{strategy.totalReturn.toFixed(1)}%</dd>
              </div>
              <div>
                <dt className="text-muted">年化</dt>
                <dd className="tnum mt-1 font-medium text-ink">{strategy.annual.toFixed(1)}%</dd>
              </div>
              <div>
                <dt className="text-muted">最大回撤</dt>
                <dd className="tnum mt-1 font-medium text-jade">{strategy.maxDrawdown.toFixed(1)}%</dd>
              </div>
              <div>
                <dt className="text-muted">夏普</dt>
                <dd className="tnum mt-1 font-medium text-ink">{strategy.sharpe.toFixed(2)}</dd>
              </div>
            </dl>
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
