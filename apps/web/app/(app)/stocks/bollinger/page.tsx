import type { Metadata } from "next";
import Link from "next/link";

import { StockSearchBox } from "@/components/stock-search-box";
import { StockSectionTabs } from "@/components/stock-section-tabs";
import { MemberGate } from "@/components/member-gate";
import { getServerToken } from "@/lib/server-auth";
import { fetchStockBollinger, type StockBand, type StockBollinger } from "@/lib/stocks";

export const metadata: Metadata = { title: "股息布林" };
export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

const RATING_STYLES: Record<string, string> = {
  回踩: "bg-jade-soft text-jade-deep",
  偏热: "bg-loss/10 text-loss",
  高位: "bg-amber-soft text-amber",
  观望: "bg-[#f1efe8] text-ink-soft",
  数据不足: "bg-line/40 text-muted",
};

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

function BandCell({ band }: { band: StockBand | null }) {
  if (!band) return <span className="text-xs text-muted">—</span>;
  return (
    <div className="text-right">
      <p className="text-xs text-ink-soft">{band.position}</p>
      <p className="tnum text-[10px] text-muted">
        {band.lower.toFixed(2)} / {band.upper.toFixed(2)}
      </p>
    </div>
  );
}

function RatingBadge({ value }: { value: string }) {
  return (
    <span
      className={`inline-block rounded-sm px-2 py-0.5 text-[11px] ${
        RATING_STYLES[value] ?? RATING_STYLES["观望"]
      }`}
    >
      {value}
    </span>
  );
}

function BollingerCard({ stock }: { stock: StockBollinger }) {
  return (
    <article className="border-b border-line p-4 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href={`/stocks/${stock.code}?tab=bollinger`} className="group">
            <span className="text-ink group-hover:text-jade-deep">{stock.name}</span>
            <span className="tnum ml-2 text-xs text-muted">{stock.code}</span>
          </Link>
          <p className="mt-1 text-xs text-muted">{stock.industry ?? "未分类"}</p>
        </div>
        <div className="text-right">
          <p className="tnum text-sm text-ink">{stock.price?.toFixed(2) ?? "—"}</p>
          <p className="tnum text-xs text-jade-deep">{pct(stock.dividend_yield_ttm)}</p>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {[
          ["日", stock.daily],
          ["周", stock.weekly],
          ["月", stock.monthly],
        ].map(([label, band]) => (
          <div key={label as string} className="rounded-sm bg-paper/70 px-2 py-2 text-center">
            <p className="text-[10px] text-muted">{label as string}布林</p>
            <p className="mt-1 text-xs text-ink-soft">
              {(band as StockBand | null)?.position ?? "—"}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-[11px] text-muted">
          {stock.change_pct == null ? "—" : `${stock.change_pct.toFixed(2)}%`}
        </span>
        <RatingBadge value={stock.rating} />
      </div>
    </article>
  );
}

export default async function StockBollingerPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const q = one(params.q);
  const industry = one(params.industry);
  const page = Math.max(1, Number(one(params.page)) || 1);

  const data = await fetchStockBollinger(
    {
      q: q || undefined,
      industry: industry || undefined,
      page,
      page_size: PAGE_SIZE,
    },
    await getServerToken(),
  );
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function pageHref(target: number): string {
    const search = new URLSearchParams();
    if (q) search.set("q", q);
    if (industry) search.set("industry", industry);
    search.set("page", String(target));
    return `/stocks/bollinger?${search.toString()}`;
  }

  return (
    <MemberGate feature="股息布林">
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">
            Bollinger Bands
          </p>
          <h1 className="mt-1 font-serif text-3xl text-ink">股息布林</h1>
          <p className="mt-1 text-sm text-muted">
            日 / 周 / 月布林位置与回踩评级 · 先覆盖已同步 K 线的股票
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StockSearchBox />
          <div className="text-right text-xs text-muted">
            <p className="tnum">共 {total.toLocaleString("zh-CN")} 只</p>
            <p>20 周期 · 2 倍标准差</p>
          </div>
        </div>
      </div>

      <StockSectionTabs active="bollinger" />

      <form
        method="get"
        action="/stocks/bollinger"
        className="card flex flex-wrap items-end gap-3 p-4 text-xs"
      >
        <label className="flex flex-col gap-1">
          <span className="text-muted">搜索</span>
          <input
            name="q"
            defaultValue={q}
            placeholder="代码或名称"
            className="w-36 rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted">行业</span>
          <input
            name="industry"
            defaultValue={industry}
            placeholder="如 金融"
            className="w-28 rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
          />
        </label>
        <button
          type="submit"
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep"
        >
          筛选
        </button>
        <Link href="/stocks/bollinger" className="pb-2 text-jade-deep hover:underline">
          重置
        </Link>
      </form>

      <div className="card overflow-hidden">
        {!data ? (
          <div className="p-8 text-center text-sm text-muted">
            布林数据暂不可用，请确认 API 已部署且个股 K 线已同步。
          </div>
        ) : data.items.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted">
            暂无足够 K 线计算布林。先对高股息股票执行 `stock-bars`。
          </div>
        ) : (
          <>
            <div className="md:hidden">
              {data.items.map((stock) => (
                <BollingerCard key={stock.code} stock={stock} />
              ))}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="border-b border-line bg-[#faf9f5] text-xs text-muted">
                  <tr>
                    <th className="px-4 py-3 font-normal">代码 / 名称</th>
                    <th className="px-4 py-3 font-normal">行业</th>
                    <th className="px-4 py-3 text-right font-normal">现价</th>
                    <th className="px-4 py-3 text-right font-normal">股息率</th>
                    <th className="px-4 py-3 text-right font-normal">涨跌</th>
                    <th className="px-4 py-3 text-right font-normal">日布林</th>
                    <th className="px-4 py-3 text-right font-normal">周布林</th>
                    <th className="px-4 py-3 text-right font-normal">月布林</th>
                    <th className="px-4 py-3 text-right font-normal">评级</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.items.map((stock) => (
                    <tr key={stock.code} className="hover:bg-black/[0.02]">
                      <td className="px-4 py-3">
                        <Link href={`/stocks/${stock.code}?tab=bollinger`} className="group">
                          <span className="tnum text-xs text-muted">{stock.code}</span>
                          <span className="ml-2 text-ink group-hover:text-jade-deep">
                            {stock.name}
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-xs text-ink-soft">
                        {stock.industry ?? "未分类"}
                      </td>
                      <td className="tnum px-4 py-3 text-right text-ink">
                        {stock.price?.toFixed(2) ?? "—"}
                      </td>
                      <td className="tnum px-4 py-3 text-right text-jade-deep">
                        {pct(stock.dividend_yield_ttm)}
                      </td>
                      <td className="tnum px-4 py-3 text-right text-xs text-muted">
                        {stock.change_pct == null ? "—" : `${stock.change_pct.toFixed(2)}%`}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <BandCell band={stock.daily} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <BandCell band={stock.weekly} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <BandCell band={stock.monthly} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <RatingBadge value={stock.rating} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {data && totalPages > 1 ? (
        <div className="flex items-center justify-between text-xs text-muted">
          <span>
            第 {page} / {totalPages} 页
          </span>
          <div className="flex gap-2">
            {page > 1 ? (
              <Link
                href={pageHref(page - 1)}
                className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink"
              >
                上一页
              </Link>
            ) : null}
            {page < totalPages ? (
              <Link
                href={pageHref(page + 1)}
                className="rounded-sm border border-line bg-surface px-3 py-1.5 hover:border-ink"
              >
                下一页
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      <p className="text-xs leading-6 text-muted">
        布林为 20 周期均线 ± 2 倍标准差，周/月由日线聚合；月线需要至少 20 个月数据。
        评级只根据布林位置规则生成，不含基本面判断，不构成投资建议。
      </p>
    </div>
    </MemberGate>
  );
}
