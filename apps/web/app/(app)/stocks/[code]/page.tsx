import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StockWatchlistButton } from "@/components/stock-watchlist-button";
import { EquityCurve } from "@/components/equity-curve";
import { fetchStock } from "@/lib/stocks";
import { fmtPct, trendClass } from "@/lib/format";

type PageProps = { params: Promise<{ code: string }> };
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { code } = await params;
  const stock = await fetchStock(code);
  return { title: stock ? `${stock.name} · 股息率` : "个股详情" };
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

function metric(value: number | null, digits = 2): string {
  return value == null ? "—" : value.toFixed(digits);
}

const SUSTAIN_LABELS: Record<string, string> = {
  stable: "连续分红",
  watch: "需核查",
  one_off: "含单次大额",
  high_yield: "高股息需核查",
  none: "无分红",
  normal: "常规",
};

export default async function StockDetailPage({ params }: PageProps) {
  const { code } = await params;
  const stock = await fetchStock(code);
  if (!stock) notFound();

  const latestDividend = stock.dividends[0];
  const annualCash = stock.dividends
    .filter((item) => item.fiscal_year === latestDividend?.fiscal_year)
    .reduce((sum, item) => sum + item.cash_per_share, 0);
  const annualTotals = Array.from(
    stock.dividends.reduce((totals, item) => {
      if (!item.fiscal_year) return totals;
      totals.set(
        item.fiscal_year,
        (totals.get(item.fiscal_year) ?? 0) + item.cash_per_share,
      );
      return totals;
    }, new Map<number, number>()),
  )
    .sort((a, b) => b[0] - a[0])
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/stocks" className="text-xs text-jade-deep hover:underline">
            ← 返回高股息列表
          </Link>
          <div className="mt-2 flex flex-wrap items-baseline gap-3">
            <h1 className="font-serif text-3xl text-ink">{stock.name}</h1>
            <span className="tnum text-sm text-muted">{stock.code}</span>
            {stock.is_st ? (
              <span className="rounded-sm bg-loss/10 px-2 py-0.5 text-[11px] text-loss">ST</span>
            ) : null}
            <span className="rounded-sm border border-line bg-surface px-2 py-0.5 text-[11px] text-muted">
              {stock.industry ?? "未分类"}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted">
            {stock.industry_path ?? "行业待补全"} · {stock.market ?? "—"}
          </p>
        </div>
        <StockWatchlistButton code={stock.code} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-5">
          <p className="text-xs text-muted">最新价</p>
          <p className="tnum mt-2 text-2xl font-semibold text-ink">
            {metric(stock.price)}
          </p>
          <p className={`tnum mt-2 text-xs ${stock.change_pct == null ? "text-muted" : trendClass(stock.change_pct)}`}>
            {stock.change_pct == null ? "—" : fmtPct(stock.change_pct)}
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">股息率 TTM</p>
          <p className="tnum mt-2 text-2xl font-semibold text-jade-deep">
            {pct(stock.dividend_yield_ttm)}
          </p>
          <p className="mt-2 text-xs text-muted">近 12 个月现金分红 / 最新价</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">最近年度股息率</p>
          <p className="tnum mt-2 text-2xl font-semibold text-ink">
            {pct(stock.dividend_yield_fy)}
          </p>
          <p className="mt-2 text-xs text-muted">最近完整年度现金分红 / 最新价</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">总市值</p>
          <p className="tnum mt-2 text-2xl font-semibold text-ink">
            {stock.market_cap == null ? "—" : `${stock.market_cap.toFixed(0)} 亿`}
          </p>
          <p className="mt-2 text-xs text-muted">
            PE {metric(stock.pe_ttm, 1)} · PB {metric(stock.pb)}
          </p>
        </div>
      </div>

      <section className="card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium text-ink">价格走势</h2>
            <p className="mt-0.5 text-xs text-muted">日线收盘价 · 最近 250 个交易日</p>
          </div>
          {stock.bars.length > 1 ? (
            <span className="tnum text-xs text-muted">
              {stock.bars[0].date} 至 {stock.bars[stock.bars.length - 1].date}
            </span>
          ) : null}
        </div>
        {stock.bars.length > 1 ? (
          <div className="mt-4">
            <EquityCurve
              id={`stock-${stock.code}`}
              points={stock.bars.map((bar) => bar.close)}
              height={180}
            />
          </div>
        ) : (
          <p className="mt-6 text-sm text-muted">
            暂无 K 线。首次加入自选或后台手动同步后生成。
          </p>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-medium text-ink">分红历史</h2>
              <p className="mt-0.5 text-xs text-muted">税前每股现金分红，按除息日倒序</p>
            </div>
            <span className="text-xs text-muted">{stock.dividends.length} 条</span>
          </div>
          {annualTotals.length > 0 ? (
            <div className="mt-4 rounded-sm border border-line bg-paper/60 p-3">
              <p className="text-[11px] text-muted">最近财年每股现金分红合计</p>
              <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-5">
                {annualTotals.map(([year, total]) => (
                  <div key={year} className="rounded-sm bg-surface px-2.5 py-2">
                    <p className="tnum text-[11px] text-muted">{year}</p>
                    <p className="tnum mt-0.5 text-sm text-ink">{total.toFixed(3)}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {stock.dividends.length === 0 ? (
            <p className="mt-6 text-sm text-muted">暂无分红记录。</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="border-b border-line text-xs text-muted">
                  <tr>
                    <th className="py-2 font-normal">除息日</th>
                    <th className="py-2 font-normal">年度</th>
                    <th className="py-2 text-right font-normal">每股现金</th>
                    <th className="py-2 font-normal">方案</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {stock.dividends.map((item) => (
                    <tr key={`${item.ex_date}-${item.plan}`}>
                      <td className="tnum py-3 text-xs text-muted">{item.ex_date}</td>
                      <td className="tnum py-3 text-xs text-ink-soft">{item.fiscal_year}</td>
                      <td className="tnum py-3 text-right text-ink">
                        {item.cash_per_share.toFixed(4)}
                      </td>
                      <td className="py-3 text-xs text-ink-soft">
                        {item.plan}
                        {item.is_special ? (
                          <span className="ml-2 rounded-sm bg-amber-soft px-1.5 py-0.5 text-[10px] text-amber">
                            特别
                          </span>
                        ) : null}
                        {item.is_one_off && !item.is_special ? (
                          <span className="ml-2 rounded-sm bg-amber-soft px-1.5 py-0.5 text-[10px] text-amber">
                            单次大额
                          </span>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="card p-5">
          <h2 className="text-base font-medium text-ink">股息摘要</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted">最近除息日</dt>
              <dd className="tnum text-ink">{stock.last_ex_date ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">最近年度</dt>
              <dd className="tnum text-ink">{latestDividend?.fiscal_year ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">年度每股现金</dt>
              <dd className="tnum text-ink">
                {latestDividend ? annualCash.toFixed(4) : "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">分红特征</dt>
              <dd className="text-ink">
                {stock.sustainability
                  ? (SUSTAIN_LABELS[stock.sustainability] ?? stock.sustainability)
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">数据更新</dt>
              <dd className="tnum text-xs text-muted">
                {stock.updated_at ? stock.updated_at.slice(0, 10) : "—"}
              </dd>
            </div>
          </dl>
          <p className="mt-5 border-t border-line pt-4 text-xs leading-6 text-muted">
            股息率随价格波动，历史分红不代表未来。数据来自公开分红公告，不构成投资建议。
          </p>
        </aside>
      </div>
    </div>
  );
}
