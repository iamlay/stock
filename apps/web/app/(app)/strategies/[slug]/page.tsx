import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { EquityCurve } from "@/components/equity-curve";
import { fetchStrategies, runBacktest } from "@/lib/api";
import { etfs, getStrategy, strategies } from "@/lib/mock";

type PageProps = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

const ENGINE_SLUGS = new Set([
  "buy-and-hold",
  "monthly-dca",
  "dual-ma",
  "rsi",
  "bollinger",
  "macd",
  "deviation",
  "grid",
]);

const PARAM_LABELS: Record<string, string> = {
  fast: "快线",
  slow: "慢线",
  period: "周期",
  oversold: "超卖线",
  overbought: "超买线",
  width: "带宽",
  window: "窗口",
  step: "步长",
  months: "定投月数",
  levels: "档位数",
};

export const dynamic = "force-dynamic";

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
  rsi: [
    "RSI 低于超卖线（默认 30）时买入。",
    "RSI 高于超买线（默认 70）时卖出。",
    "中间区间保持当前仓位，不频繁交易。",
  ],
  bollinger: [
    "收盘跌破布林带下轨时买入。",
    "收盘回到中轨上方时卖出。",
    "带宽随波动放大，震荡市信号更多。",
  ],
  macd: [
    "DIF 上穿 DEA（金叉）时买入。",
    "DIF 下穿 DEA（死叉）时卖出。",
    "默认参数 12 / 26 / 9。",
  ],
  deviation: [
    "收盘价低于均线时，按偏离幅度提高目标仓位。",
    "正偏离超过阈值时逐步减仓。",
    "每日只买卖目标仓位与当前仓位的差额，允许长期半仓。",
  ],
  grid: [
    "取最近 N 个交易日的最高价与最低价，等分为若干档。",
    "价格越接近区间下沿，目标仓位越高；越接近上沿，仓位越低。",
    "每天只调整目标仓位与当前仓位的差额。",
  ],
};

export default async function StrategyDetailPage({ params, searchParams }: PageProps) {
  const { slug } = await params;
  const strategy = getStrategy(slug);
  if (!strategy) notFound();

  const query = await searchParams;
  const rawCode = Array.isArray(query.code) ? query.code[0] : query.code;
  const rawStart = Array.isArray(query.start) ? query.start[0] : query.start;
  const code = etfs.some((etf) => etf.code === rawCode) ? rawCode! : "510300";
  const start = rawStart && /^\d{4}-\d{2}-\d{2}$/.test(rawStart) ? rawStart : "2020-01-01";

  const catalog = await fetchStrategies();
  const spec = catalog?.find((item) => item.slug === slug);
  const strategyParams: Record<string, number> = {};
  if (spec) {
    for (const [key, rule] of Object.entries(spec.params)) {
      const raw = Array.isArray(query[key]) ? query[key]?.[0] : query[key];
      const value = Number(raw ?? rule.default ?? 0);
      if (Number.isFinite(value)) strategyParams[key] = value;
    }
  }

  const headerBag = await headers();
  const forwardedFor = headerBag.get("x-forwarded-for") ?? "";
  const outcome = ENGINE_SLUGS.has(slug)
    ? await runBacktest(
        {
          code,
          strategy: slug,
          start,
          end: new Date().toISOString().slice(0, 10),
          params: strategyParams,
        },
        { forwardedFor },
      )
    : null;

  const live = outcome?.ok ? outcome.result : null;
  const backtestError = outcome && !outcome.ok ? outcome.error : null;
  const quota = outcome?.ok ? outcome.quota : outcome?.quota ?? null;

  const metrics: { label: string; value: string; tone?: string }[] = live
    ? [
        {
          label: "累计收益",
          value: `${live.metrics.total_return > 0 ? "+" : ""}${live.metrics.total_return}%`,
          tone: live.metrics.total_return >= 0 ? "text-loss" : "text-jade",
        },
        {
          label: "年化收益",
          value: `${live.metrics.annualized_return > 0 ? "+" : ""}${live.metrics.annualized_return}%`,
        },
        {
          label: "最大回撤",
          value: `${live.metrics.max_drawdown}%`,
          tone: "text-jade",
        },
        { label: "夏普比率", value: live.metrics.sharpe.toFixed(2) },
        { label: "交易次数", value: String(live.metrics.trades) },
        {
          label: "胜率",
          value: live.metrics.win_rate == null ? "—" : `${live.metrics.win_rate}%`,
        },
      ]
    : [
        { label: "累计收益", value: `+${strategy.totalReturn.toFixed(1)}%`, tone: "text-loss" },
        { label: "年化收益", value: `${strategy.annual.toFixed(1)}%` },
        { label: "最大回撤", value: `${strategy.maxDrawdown.toFixed(1)}%`, tone: "text-jade" },
        { label: "夏普比率", value: strategy.sharpe.toFixed(2) },
        { label: "交易次数", value: String(strategy.trades) },
        { label: "胜率", value: "—" },
      ];

  const points = live ? live.equity.map((point) => point.equity) : strategy.curve;
  const chartNote = live
    ? `${live.start} → ${live.end} · 初始资金 10 万 · T+1 开盘成交`
    : "示例数据 · 未连接回测引擎";

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
        <span className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-muted">
          {live ? "引擎实时计算" : backtestError ? "额度受限" : "示例结果"}
        </span>
      </div>

      {ENGINE_SLUGS.has(slug) ? (
        <form
          method="get"
          className="card flex flex-wrap items-end gap-3 p-4 text-sm"
          action={`/strategies/${slug}`}
        >
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted">标的</span>
            <select
              name="code"
              defaultValue={code}
              className="rounded-sm border border-line bg-surface px-3 py-2 text-sm"
            >
              {etfs.map((etf) => (
                <option key={etf.code} value={etf.code}>
                  {etf.code} {etf.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted">起始日期</span>
            <input
              type="date"
              name="start"
              defaultValue={start}
              className="rounded-sm border border-line bg-surface px-3 py-2 text-sm"
            />
          </label>
          {spec
            ? Object.entries(spec.params).map(([key, rule]) => (
                <label key={key} className="flex w-24 flex-col gap-1">
                  <span className="text-xs text-muted">{PARAM_LABELS[key] ?? key}</span>
                  <input
                    type="number"
                    name={key}
                    defaultValue={strategyParams[key]}
                    min={rule.min}
                    max={rule.max}
                    step={rule.type === "integer" ? 1 : "any"}
                    className="w-full rounded-sm border border-line bg-surface px-2 py-2 text-sm"
                  />
                </label>
              ))
            : null}
          <button
            type="submit"
            className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep"
          >
            运行回测
          </button>
          <span className="text-xs text-muted">
            {quota
              ? quota.limit == null
                ? `会员不限次数 · 今日已用 ${quota.used} 次`
                : `今日剩余 ${quota.remaining}/${quota.limit} 次`
              : live
                ? `数据 ${live.start} → ${live.end}`
                : "API 不可用时回退示例"}
          </span>
        </form>
      ) : null}

      {backtestError ? (
        <div className="rounded-sm border border-amber/30 bg-amber-soft/60 p-4 text-sm leading-6 text-amber">
          {backtestError}
          <Link href="/pricing" className="ml-2 underline">
            了解会员
          </Link>
        </div>
      ) : null}

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
            <p className="mt-0.5 text-xs text-muted">{chartNote}</p>
          </div>
          <div className="text-right text-[11px] text-muted">
            净值（元）· 初始 10 万
          </div>
        </div>
        <div className="mt-6">
          {points.length > 1 ? (
            <EquityCurve id={`detail-${slug}`} points={points} height={260} />
          ) : (
            <p className="py-16 text-center text-sm text-muted">回测区间内没有足够数据。</p>
          )}
        </div>
      </section>

      {live && live.trades.length > 0 ? (
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium text-ink">最近交易</h2>
            <span className="text-xs text-muted">共 {live.trades.length} 笔</span>
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="py-2 font-medium">日期</th>
                  <th className="py-2 font-medium">方向</th>
                  <th className="py-2 text-right font-medium">价格</th>
                  <th className="py-2 text-right font-medium">份额</th>
                  <th className="py-2 text-right font-medium">费用</th>
                  <th className="py-2 text-right font-medium">已实现盈亏</th>
                </tr>
              </thead>
              <tbody>
                {live.trades.slice(-12).map((trade, index) => (
                  <tr key={`${trade.date}-${index}`} className="border-b border-line/60">
                    <td className="py-2 text-ink-soft">{trade.date}</td>
                    <td className={`py-2 ${trade.side === "buy" ? "text-loss" : "text-jade"}`}>
                      {trade.side === "buy" ? "买入" : "卖出"}
                    </td>
                    <td className="tnum py-2 text-right">{trade.price}</td>
                    <td className="tnum py-2 text-right">{trade.shares}</td>
                    <td className="tnum py-2 text-right text-muted">{trade.fee}</td>
                    <td className="tnum py-2 text-right">
                      {trade.realized_pnl == null ? "—" : trade.realized_pnl}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="text-base font-medium text-ink">规则说明</h2>
          <ul className="mt-4 space-y-3">
            {(rules[slug] ?? []).map((rule) => (
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
              ["成交时点", "T+1 开盘"],
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

      <p className="text-xs leading-6 text-muted">
        历史回测，非实盘承诺，不构成投资建议。回测未计入申购赎回费、冲击成本与税费，实盘结果可能显著不同。
      </p>
    </div>
  );
}
