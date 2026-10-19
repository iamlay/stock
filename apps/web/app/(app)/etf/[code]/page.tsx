import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { EquityCurve } from "@/components/equity-curve";
import { fetchEtf } from "@/lib/api";
import { etfs, getEtf, strategies } from "@/lib/mock";
import { fmtNumber, fmtPct, trendClass } from "@/lib/format";

type PageProps = { params: Promise<{ code: string }> };

export const dynamicParams = false;
export const revalidate = 60;

export function generateStaticParams() {
  return etfs.map((etf) => ({ code: etf.code }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { code } = await params;
  const api = await fetchEtf(code);
  const fallback = getEtf(code);
  const name = api?.name ?? fallback?.name;
  if (!name) return { title: "ETF 未找到" };
  return {
    title: `${name}（${code}）`,
    description: `${name} 的行情、规模、均线、回撤与份额数据。`,
  };
}

function demoCurve(seed: number): number[] {
  return Array.from({ length: 24 }, (_, index) => {
    const drift = index * 0.9;
    const wave = Math.sin((index + seed) / 2.4) * 4;
    return Number((100 + drift + wave).toFixed(2));
  });
}

export default async function EtfDetailPage({ params }: PageProps) {
  const { code } = await params;
  const api = await fetchEtf(code);
  const fallback = getEtf(code);
  if (!api && !fallback) notFound();

  const name = api?.name ?? fallback!.name;
  const category = api?.category ?? fallback!.category;
  const price = api?.price ?? fallback!.price;
  const change = api?.change_pct ?? fallback!.change;
  const aum = api?.aum ?? fallback!.aum;
  const shares = api?.shares ?? (aum !== null ? aum / price : null);
  const live = api !== null;

  const points =
    api && api.bars.length > 0
      ? api.bars.map((bar) => bar.close)
      : demoCurve(fallback?.pePercentile ?? 30);
  const chartNote =
    api && api.bars.length > 0
      ? `近 ${api.bars.length} 个交易日 · 前复权`
      : "近 24 个月 · 示例";

  const metrics: { label: string; value: string; tone?: string }[] = [
    { label: "最新价", value: fmtNumber(price, 3) },
    { label: "日涨跌", value: fmtPct(change), tone: trendClass(change) },
    { label: "规模", value: aum === null ? "—" : `${fmtNumber(aum, 1)} 亿` },
    { label: "份额", value: shares === null ? "—" : `${fmtNumber(shares, 1)} 亿份` },
    { label: "MA20", value: api?.ma20 == null ? "—" : fmtNumber(api.ma20, 3) },
    {
      label: "近 1 年回撤",
      value: api?.max_drawdown_1y == null ? "—" : `${api.max_drawdown_1y.toFixed(1)}%`,
    },
  ];

  return (
    <div className="space-y-6">
      <nav className="text-xs text-muted">
        <Link href="/etf" className="hover:text-ink">
          ETF 数据
        </Link>
        <span className="mx-1.5">/</span>
        <span>{category}</span>
        <span className="mx-1.5">/</span>
        <span className="text-ink">{code}</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-3xl text-ink">{name}</h1>
            <span className="rounded-sm bg-jade-soft px-2 py-0.5 text-[11px] text-jade-deep">
              {category}
            </span>
          </div>
          <p className="tnum mt-1 text-sm text-muted">{code}</p>
        </div>
        <div className="text-right">
          <p className="tnum text-3xl font-semibold text-ink">{fmtNumber(price, 3)}</p>
          <p className={`tnum mt-1 text-sm ${trendClass(change)}`}>{fmtPct(change)}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-medium text-ink">净值走势</h2>
              <p className="mt-0.5 text-xs text-muted">{chartNote}</p>
            </div>
            <span className="rounded-sm border border-line px-2 py-1 text-[11px] text-muted">
              {live ? "日线" : "示例"}
            </span>
          </div>
          <div className="mt-6">
            <EquityCurve id={`etf-${code}`} points={points} height={240} stroke="#0b7a5c" />
          </div>
          {live ? (
            <dl className="mt-4 grid grid-cols-4 gap-2 border-t border-line pt-4 text-xs">
              {[
                ["近 1 月", api?.return_1m],
                ["近 3 月", api?.return_3m],
                ["近 1 年", api?.return_1y],
                ["年化波动", api?.volatility_20d],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-muted">{label}</dt>
                  <dd
                    className={`tnum mt-1 font-medium ${
                      typeof value === "number" && value > 0 ? "text-loss" : "text-ink"
                    }`}
                  >
                    {typeof value === "number" ? `${value > 0 ? "+" : ""}${value}%` : "—"}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </section>

        <section className="card p-5">
          <h2 className="text-base font-medium text-ink">关键指标</h2>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-4">
            {metrics.map((metric) => (
              <div key={metric.label}>
                <dt className="text-xs text-muted">{metric.label}</dt>
                <dd className={`tnum mt-1 text-sm font-medium ${metric.tone ?? "text-ink"}`}>
                  {metric.value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-5 border-t border-line pt-4 text-[11px] leading-5 text-muted">
            {live
              ? `均线与回撤按最近 260 个交易日计算；份额来自交易所快照${
                  api?.fee_rate ? `；管理费率 ${api.fee_rate}%` : ""
                }。`
              : "示例数据。启动 API 与数据管道后自动切换为真实行情。"}
          </p>
        </section>
      </div>

      <section className="card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium text-ink">相关策略</h2>
          <Link href="/strategies" className="text-xs text-jade-deep hover:underline">
            全部策略 →
          </Link>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {strategies.slice(1, 3).map((strategy) => (
            <Link
              key={strategy.slug}
              href={`/strategies/${strategy.slug}`}
              className="flex items-center justify-between rounded-sm border border-line p-4 transition-colors hover:border-jade/50"
            >
              <div>
                <p className="text-sm font-medium text-ink">{strategy.name}</p>
                <p className="mt-1 text-xs text-muted">
                  最大回撤 {strategy.maxDrawdown.toFixed(1)}%
                </p>
              </div>
              <span className="tnum text-sm text-loss">+{strategy.totalReturn.toFixed(1)}%</span>
            </Link>
          ))}
        </div>
      </section>

      <p className="text-xs leading-6 text-muted">
        {live ? `数据更新至 ${api?.trade_date}。` : ""}
        以上不构成投资建议。ETF 存在跟踪误差、折溢价与流动性风险，历史表现不代表未来收益。
      </p>
    </div>
  );
}
