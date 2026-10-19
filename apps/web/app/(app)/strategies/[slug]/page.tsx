import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { EquityCurve } from "@/components/equity-curve";
import { getStrategy, strategies } from "@/lib/mock";

type PageProps = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return strategies.map((strategy) => ({ slug: strategy.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const strategy = getStrategy(slug);
  return { title: strategy ? strategy.name : "策略未找到" };
}

const rules: Record<string, string[]> = {
  "buy-and-hold": [
    "回测起点一次性全仓买入，之后不再交易。",
    "唯一一笔买入按 T+1 开盘价成交，计入佣金与滑点。",
    "分红按除权日再投资，净值使用后复权计算。",
  ],
  "monthly-dca": [
    "每月第一个交易日收盘后计算信号，次一交易日开盘买入固定金额。",
    "不设卖出规则，仓位随定投逐步累积。",
    "可设置资金上限，达到上限后停止买入。",
  ],
  "dual-ma": [
    "快线（默认 20 日）上穿慢线（默认 60 日）时买入。",
    "快线下穿慢线时清仓卖出。",
    "全仓进出，不设分批加减仓。",
  ],
  deviation: [
    "收盘价低于均线时，按偏离幅度提高目标仓位。",
    "正偏离超过阈值时逐步减仓。",
    "每日只买卖目标仓位与当前仓位的差额，允许长期半仓。",
  ],
};

export default async function StrategyDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const strategy = getStrategy(slug);
  if (!strategy) notFound();

  const metrics: { label: string; value: string; tone?: string }[] = [
    { label: "累计收益", value: `+${strategy.totalReturn.toFixed(1)}%`, tone: "text-loss" },
    { label: "年化收益", value: `${strategy.annual.toFixed(1)}%` },
    { label: "最大回撤", value: `${strategy.maxDrawdown.toFixed(1)}%`, tone: "text-jade" },
    { label: "夏普比率", value: strategy.sharpe.toFixed(2) },
    { label: "交易次数", value: String(strategy.trades) },
    { label: "仓位方式", value: strategy.tag === "仓位" ? "连续调仓" : strategy.tag === "定投" ? "分批买入" : "全仓进出" },
  ];

  return (
    <div className="space-y-6">
      <nav className="text-xs text-muted">
        <Link href="/strategies" className="hover:text-ink">
          策略实验室
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-ink">{strategy.name}</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-serif text-3xl text-ink">{strategy.name}</h1>
            <span className="rounded-sm bg-jade-soft px-2 py-0.5 text-[11px] text-jade-deep">
              {strategy.tag}
            </span>
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">{strategy.summary}</p>
        </div>
        <button
          type="button"
          className="rounded-sm border border-line bg-surface px-4 py-2 text-xs text-muted"
          disabled
          title="参数面板将在 W8 接入"
        >
          参数面板 · 即将上线
        </button>
      </div>

      <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {metrics.map((metric) => (
          <div key={metric.label} className="card p-4">
            <p className="text-xs text-muted">{metric.label}</p>
            <p className={`tnum mt-2 text-lg font-semibold ${metric.tone ?? "text-ink"}`}>
              {metric.value}
            </p>
          </div>
        ))}
      </section>

      <section className="card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium text-ink">净值曲线</h2>
            <p className="mt-0.5 text-xs text-muted">策略 vs 基准（买入持有）· 示例数据</p>
          </div>
          <div className="flex items-center gap-4 text-[11px] text-muted">
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 bg-jade" /> 策略
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 bg-line" /> 基准
            </span>
          </div>
        </div>
        <div className="mt-6">
          <EquityCurve id={`detail-${strategy.slug}`} points={strategy.curve} height={260} />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="text-base font-medium text-ink">规则说明</h2>
          <ul className="mt-4 space-y-3">
            {(rules[strategy.slug] ?? []).map((rule) => (
              <li key={rule} className="flex gap-2 text-sm leading-6 text-ink-soft">
                <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-jade" />
                {rule}
              </li>
            ))}
          </ul>
        </section>

        <section className="card p-5">
          <h2 className="text-base font-medium text-ink">成交假设</h2>
          <dl className="mt-4 space-y-3 text-sm">
            {[
              ["信号时点", "T 日收盘后"],
              ["成交时点", "T+1 开盘（默认）"],
              ["成本", "佣金 0.02%（最低 5 元）+ 滑点 2bp"],
              ["约束", "T+1、100 份整数倍、停牌/涨跌停不成交"],
              ["复权", "后复权，分红再投"],
            ].map(([label, value]) => (
              <div key={label} className="flex items-start justify-between gap-4">
                <dt className="shrink-0 text-muted">{label}</dt>
                <dd className="text-right text-ink">{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <section className="rounded-sm border border-amber/20 bg-amber-soft/50 p-5">
        <p className="text-sm font-medium text-amber">下一交易日推演</p>
        <p className="mt-2 text-sm leading-6 text-ink-soft">
          按最新收盘数据，当前策略未触发调仓信号。此处将在 W8 接入实时参数与推演接口，并明确标注「规则推演，非下单指令」。
        </p>
      </section>

      <p className="text-xs leading-6 text-muted">
        历史回测，非实盘承诺，不构成投资建议。回测未计入申购赎回费、冲击成本与税费，实盘结果可能显著不同。
      </p>
    </div>
  );
}
