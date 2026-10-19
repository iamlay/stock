import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { EquityCurve } from "@/components/equity-curve";
import { etfs, getEtf, strategies } from "@/lib/mock";
import { fmtNumber, fmtPct, trendClass } from "@/lib/format";

type PageProps = { params: Promise<{ code: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return etfs.map((etf) => ({ code: etf.code }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { code } = await params;
  const etf = getEtf(code);
  if (!etf) return { title: "ETF 未找到" };
  return {
    title: `${etf.name}（${etf.code}）`,
    description: `${etf.name} 的行情、规模、股息率与估值分位。示例数据，接入真实数据后更新。`,
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
  const etf = getEtf(code);
  if (!etf) notFound();

  const shares = etf.aum / etf.price;

  const metrics: { label: string; value: string; tone?: string }[] = [
    { label: "最新价", value: fmtNumber(etf.price, 3) },
    { label: "日涨跌", value: fmtPct(etf.change), tone: trendClass(etf.change) },
    { label: "规模", value: `${fmtNumber(etf.aum, 1)} 亿` },
    { label: "估算份额", value: `${fmtNumber(shares, 1)} 亿份` },
    {
      label: "股息率",
      value: etf.dividendYield === null ? "—" : `${etf.dividendYield.toFixed(1)}%`,
    },
    { label: "估值分位", value: `${etf.pePercentile}%` },
  ];

  return (
    <div className="space-y-6">
      <nav className="text-xs text-muted">
        <Link href="/etf" className="hover:text-ink">
          ETF 数据
        </Link>
        <span className="mx-1.5">/</span>
        <span>{etf.category}</span>
        <span className="mx-1.5">/</span>
        <span className="text-ink">{etf.code}</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-3xl text-ink">{etf.name}</h1>
            <span className="rounded-sm bg-jade-soft px-2 py-0.5 text-[11px] text-jade-deep">
              {etf.category}
            </span>
          </div>
          <p className="tnum mt-1 text-sm text-muted">{etf.code}</p>
        </div>
        <div className="text-right">
          <p className="tnum text-3xl font-semibold text-ink">{fmtNumber(etf.price, 3)}</p>
          <p className={`tnum mt-1 text-sm ${trendClass(etf.change)}`}>{fmtPct(etf.change)}</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-medium text-ink">净值走势</h2>
              <p className="mt-0.5 text-xs text-muted">近 24 个月 · 后复权 · 示例</p>
            </div>
            <span className="rounded-sm border border-line px-2 py-1 text-[11px] text-muted">月线</span>
          </div>
          <div className="mt-6">
            <EquityCurve
              id={`etf-${etf.code}`}
              points={demoCurve(etf.pePercentile)}
              height={240}
              stroke="#0b7a5c"
            />
          </div>
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
            管理费率 0.50%（示例）。估值分位为近 5 年 PE 分位；份额为规模 / 净值估算，接入交易所数据后以实际份额为准。
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
                <p className="mt-1 text-xs text-muted">最大回撤 {strategy.maxDrawdown.toFixed(1)}%</p>
              </div>
              <span className="tnum text-sm text-loss">+{strategy.totalReturn.toFixed(1)}%</span>
            </Link>
          ))}
        </div>
      </section>

      <p className="text-xs leading-6 text-muted">
        以上为示例数据，不构成投资建议。ETF 存在跟踪误差、折溢价与流动性风险，历史表现不代表未来收益。
      </p>
    </div>
  );
}
