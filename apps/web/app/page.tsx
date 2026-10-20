import Link from "next/link";

import { EquityCurve } from "@/components/equity-curve";
import { EtfTable } from "@/components/etf-table";
import { SiteFooter, SiteHeader } from "@/components/chrome";
import { TickerStrip } from "@/components/ticker-strip";
import { fetchEtf, fetchEtfs, fetchStrategySummaries, toEtf } from "@/lib/api";
import { etfs, strategies } from "@/lib/mock";

export const revalidate = 60;

const features = [
  {
    index: "01",
    title: "每个数字都能解释",
    body: "涨跌幅、估值分位、股息率、折溢价，全部附口径、样本区间与更新时间。看不懂的指标，点开就有白话说明。",
    tag: "数据可信",
  },
  {
    index: "02",
    title: "回测不许有未来函数",
    body: "信号在收盘后计算，默认次日开盘成交；停牌、涨跌停、分红再投、手续费全部计入。规则与成交假设公开可查。",
    tag: "策略透明",
  },
  {
    index: "03",
    title: "先想回撤，再谈收益",
    body: "红利、现金流、跨境、宽基四类 ETF 横向对比，把最大回撤和持有体验放在收益前面。",
    tag: "稳健优先",
  },
];

export default async function HomePage() {
  const [apiEtfs, heroApi, strategySummary] = await Promise.all([
    fetchEtfs(),
    fetchEtf("510300"),
    fetchStrategySummaries("510300"),
  ]);
  const live = Boolean(apiEtfs?.length);
  const list = apiEtfs && apiEtfs.length > 0 ? apiEtfs.map(toEtf) : etfs;
  const featured = [...list]
    .sort((a, b) => (b.aum ?? 0) - (a.aum ?? 0))
    .slice(0, 6);
  const tickerItems = list.slice(0, 6).map((item) => ({
    name: item.name,
    value: item.price,
    change: item.change,
  }));

  const flagshipItem =
    strategySummary?.items.find((item) => item.slug === "deviation") ??
    strategySummary?.items[0];
  const flagship = flagshipItem
    ? {
        name: flagshipItem.name,
        totalReturn: flagshipItem.total_return,
        maxDrawdown: flagshipItem.max_drawdown,
        sharpe: flagshipItem.sharpe,
        trades: flagshipItem.trades,
        curve: flagshipItem.curve,
        tag: "实测",
      }
    : (() => {
        const fallback =
          strategies.find((item) => item.slug === "deviation") ?? strategies[0];
        return {
          name: fallback.name,
          totalReturn: fallback.totalReturn,
          maxDrawdown: fallback.maxDrawdown,
          sharpe: fallback.sharpe,
          trades: fallback.trades,
          curve: fallback.curve,
          tag: fallback.tag,
        };
      })();

  const heroPercentile = heroApi?.pe_percentile ?? null;
  const heroCurve =
    heroApi && heroApi.bars.length > 1
      ? heroApi.bars.map((bar) => bar.close)
      : [100, 97, 101, 99, 104, 108, 106, 111, 109, 114, 118, 115, 121, 119, 124, 128, 126, 131, 129, 134];
  const heroDate = heroApi?.trade_date ?? null;

  return (
    <div className="min-h-screen">
      <SiteHeader />
      <TickerStrip items={tickerItems} />

      <main>
        <section className="relative overflow-hidden border-b border-line">
          <div className="grid-paper pointer-events-none absolute inset-0 opacity-70" />
          <div className="relative mx-auto grid max-w-6xl gap-12 px-6 pb-16 pt-16 lg:grid-cols-[1.15fr_0.85fr] lg:items-center lg:pb-20 lg:pt-20">
            <div>
              <p className="inline-flex items-center gap-2 rounded-sm border border-line bg-surface px-2.5 py-1 text-xs text-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-jade" />
                {live ? `真实数据 · ${heroDate ?? "日线"}` : "产品演示 · 非实时行情"}
              </p>
              <h1 className="mt-6 font-serif text-[36px] leading-[1.15] tracking-tight text-ink sm:text-[52px] lg:text-[56px]">
                先把回撤想清楚，
                <br />
                <span className="text-jade-deep">再谈收益。</span>
              </h1>
              <p className="mt-6 max-w-xl text-[15px] leading-7 text-ink-soft">
                StockLab 是一个面向稳健型投资者的 ETF 投研台：把市场温度、估值位置、份额变化和策略规则放在同一张桌上，让你自己判断，而不是听人喊单。
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link
                  href="/dashboard"
                  className="rounded-sm bg-ink px-5 py-3 text-sm font-medium text-paper transition-colors hover:bg-jade-deep"
                >
                  进入今日市场
                </Link>
                <Link
                  href="/strategies"
                  className="rounded-sm border border-line bg-surface px-5 py-3 text-sm font-medium text-ink transition-colors hover:border-ink"
                >
                  看策略实验室
                </Link>
              </div>
              <dl className="mt-10 grid max-w-lg grid-cols-2 gap-x-8 gap-y-4 border-t border-line pt-6 sm:grid-cols-4">
                {[
                  ["20", "重点 ETF"],
                  ["8", "规则策略"],
                  ["10 年", "日线回测"],
                  ["18:30", "每日更新"],
                ].map(([value, label]) => (
                  <div key={label}>
                    <dt className="text-xs text-muted">{label}</dt>
                    <dd className="tnum mt-1 text-lg font-semibold text-ink">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="relative">
              <div className="card p-5 shadow-[0_24px_60px_-40px_rgba(18,24,31,0.5)]">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-muted">沪深300ETF · 估值位置</p>
                    <p className="tnum mt-1 text-3xl font-semibold text-ink">
                      {heroPercentile === null ? "—" : heroPercentile}
                      <span className="ml-0.5 text-base font-normal text-muted">%</span>
                    </p>
                  </div>
                  <span className="rounded-sm bg-jade-soft px-2 py-1 text-[11px] text-jade-deep">
                    近 5 年分位
                  </span>
                </div>
                <div className="mt-4">
                  <EquityCurve
                    id="hero-curve"
                    points={heroCurve}
                    height={150}
                  />
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-4 text-xs">
                  <div>
                    <p className="text-muted">PE（TTM）</p>
                    <p className="tnum mt-1 text-sm font-medium text-ink">
                      {heroApi?.pe == null ? "—" : heroApi.pe.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted">股息率</p>
                    <p className="tnum mt-1 text-sm font-medium text-ink">
                      {heroApi?.dividend_yield == null
                        ? "—"
                        : `${heroApi.dividend_yield.toFixed(2)}%`}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted">近 1 年</p>
                    <p className="tnum mt-1 text-sm font-medium text-ink">
                      {heroApi?.return_1y == null
                        ? "—"
                        : `${heroApi.return_1y >= 0 ? "+" : ""}${heroApi.return_1y.toFixed(1)}%`}
                    </p>
                  </div>
                </div>
              </div>
              <div className="absolute -bottom-4 -left-4 hidden rounded-sm border border-line bg-surface px-3 py-2 text-[11px] text-muted shadow-sm sm:block">
                日线 · 非实时行情
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-line bg-surface">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">Why StockLab</p>
                <h2 className="mt-2 font-serif text-3xl text-ink">把"看不懂"当成产品缺陷</h2>
              </div>
              <p className="max-w-sm text-sm leading-6 text-muted">
                大部分投研工具在堆指标。我们更在意：这个数字怎么来的，你现在该看哪一个。
              </p>
            </div>
            <div className="mt-10 grid gap-px overflow-hidden rounded-sm border border-line bg-line md:grid-cols-3">
              {features.map((feature) => (
                <article key={feature.index} className="bg-surface p-6">
                  <div className="flex items-center justify-between">
                    <span className="tnum text-xs text-muted">{feature.index}</span>
                    <span className="rounded-sm bg-jade-soft px-2 py-0.5 text-[11px] text-jade-deep">
                      {feature.tag}
                    </span>
                  </div>
                  <h3 className="mt-6 text-lg font-medium text-ink">{feature.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-ink-soft">{feature.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-line">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">ETF Universe</p>
                <h2 className="mt-2 font-serif text-3xl text-ink">重点 ETF，一眼横评</h2>
              </div>
              <Link href="/etf" className="text-sm text-jade-deep hover:underline">
                查看全部 20 只 →
              </Link>
            </div>
            <div className="card mt-8 p-2 sm:p-4">
              <EtfTable rows={featured} />
            </div>
            <p className="mt-3 text-xs text-muted">
              {live
                ? `按最新规模排序，行情更新至 ${apiEtfs?.[0]?.trade_date ?? "最近交易日"}；估值分位为近 5 年 PE 分位。`
                : "演示数据：API 未连接时使用界面占位，连通后自动替换。"}
            </p>
          </div>
        </section>

        <section className="bg-ink text-paper">
          <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">Strategy Lab</p>
              <h2 className="mt-3 font-serif text-3xl leading-snug">
                规则写清楚，
                <br />
                结果才值得信。
              </h2>
              <p className="mt-4 max-w-md text-sm leading-6 text-paper/70">
                8 个规则策略，参数可改、成交可查。信号在 T 日收盘后计算，T+1 开盘成交，杜绝"收盘信号、收盘成交"的未来函数。
              </p>
              <Link
                href="/strategies"
                className="mt-7 inline-flex rounded-sm bg-paper px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:bg-jade-soft"
              >
                打开策略实验室
              </Link>
            </div>
            <div className="rounded-sm border border-white/10 bg-white/[0.04] p-5">
              <div className="flex items-baseline justify-between">
                <div>
                  <p className="text-sm text-paper/60">{flagship.name}</p>
                  <p className="tnum mt-1 text-2xl font-semibold text-paper">
                    {flagship.totalReturn >= 0 ? "+" : ""}
                    {flagship.totalReturn.toFixed(1)}%
                    <span className="ml-2 text-xs font-normal text-paper/50">累计收益</span>
                  </p>
                </div>
                <span className="rounded-sm border border-white/15 px-2 py-1 text-[11px] text-paper/70">
                  {flagship.tag}
                </span>
              </div>
              <div className="mt-4">
                <EquityCurve
                  id="home-strategy-curve"
                  points={flagship.curve}
                  height={170}
                  stroke="#5fd3ac"
                  fill="rgba(95, 211, 172, 0.16)"
                />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3 border-t border-white/10 pt-4 text-xs">
                <div>
                  <p className="text-paper/50">最大回撤</p>
                  <p className="tnum mt-1 text-paper">{flagship.maxDrawdown.toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-paper/50">夏普</p>
                  <p className="tnum mt-1 text-paper">{flagship.sharpe.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-paper/50">调仓次数</p>
                  <p className="tnum mt-1 text-paper">{flagship.trades}</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-line">
          <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 md:grid-cols-2">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">Pricing</p>
              <h2 className="mt-2 font-serif text-3xl text-ink">先试用，再决定</h2>
              <p className="mt-4 max-w-md text-sm leading-6 text-ink-soft">
                内测阶段采用邀请制。会员通过第三方平台购买后获得兑换码，在站内开通，不接入微信登录与微信支付。
              </p>
              <Link href="/pricing" className="mt-6 inline-block text-sm text-jade-deep hover:underline">
                查看会员权益与兑换方式 →
              </Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="card p-5">
                <p className="text-sm font-medium text-ink">7 天试用</p>
                <p className="tnum mt-2 text-2xl font-semibold text-ink">¥0</p>
                <p className="mt-3 text-xs leading-5 text-muted">全功能体验，含 5 次/日回测</p>
              </div>
              <div className="card border-jade/40 bg-jade-soft/50 p-5">
                <p className="text-sm font-medium text-jade-deep">标准年付</p>
                <p className="tnum mt-2 text-2xl font-semibold text-ink">
                  ¥199
                  <span className="ml-1 text-xs font-normal text-muted line-through">¥299</span>
                </p>
                <p className="mt-3 text-xs leading-5 text-muted">早鸟价 · 行情 + ETF + 20 次/日回测</p>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-line bg-jade-soft/40">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-6 py-8 text-sm sm:flex-row sm:items-center">
            <p className="leading-6 text-ink-soft">
              {live
                ? "行情与回测来自本地数据管道；所有策略为历史规则推演，不构成投资建议。"
                : "API 未连接，页面部分数据为示例；所有策略为历史规则推演，不构成投资建议。"}
            </p>
            <Link href="/login" className="shrink-0 text-jade-deep hover:underline">
              已有邀请码？去登录 →
            </Link>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
