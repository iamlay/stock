"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  fetchMe,
  fetchStockWatchlist,
  fetchWatchlist,
  getToken,
  removeStockWatchlist,
  removeWatchlist,
} from "@/lib/auth";
import type { ApiEtf } from "@/lib/api";
import type { Stock } from "@/lib/stocks";
import { fmtNumber, fmtPct, trendClass } from "@/lib/format";

export default function WatchlistPage() {
  const router = useRouter();
  const [items, setItems] = useState<ApiEtf[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const [etfs, stockItems] = await Promise.all([
      fetchWatchlist(),
      fetchStockWatchlist(),
    ]);
    setItems(etfs);
    setStocks(stockItems);
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    fetchMe()
      .then(load)
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function onRemove(code: string) {
    setError(null);
    try {
      await removeWatchlist(code);
      setItems((current) => current.filter((item) => item.code !== code));
    } catch (err) {
      setError(err instanceof Error ? err.message : "移除失败");
    }
  }

  async function onRemoveStock(code: string) {
    setError(null);
    try {
      await removeStockWatchlist(code);
      setStocks((current) => current.filter((item) => item.code !== code));
    } catch (err) {
      setError(err instanceof Error ? err.message : "移除失败");
    }
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">我的自选</h1>
          <p className="mt-1 text-sm text-muted">
            跟踪你关注的 ETF 与个股，共 {items.length} 只 ETF、{stocks.length} 只个股
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/etf/compare"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            去对比
          </Link>
          <Link
            href="/stocks"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            去高股息
          </Link>
          <Link
            href="/etf"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            去 ETF 列表添加
          </Link>
        </div>
      </div>

      {error ? <p className="text-xs text-loss">{error}</p> : null}

      <section className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">名称</th>
                <th className="px-4 py-3 font-medium">分类</th>
                <th className="px-4 py-3 text-right font-medium">最新价</th>
                <th className="px-4 py-3 text-right font-medium">日涨跌</th>
                <th className="px-4 py-3 text-right font-medium">MA20</th>
                <th className="px-4 py-3 text-right font-medium">规模</th>
                <th className="px-4 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.code} className="border-b border-line/60">
                  <td className="px-4 py-3">
                    <Link
                      href={`/etf/${item.code}`}
                      className="font-medium text-ink hover:text-jade-deep"
                    >
                      {item.name}
                    </Link>
                    <p className="tnum mt-0.5 text-[11px] text-muted">{item.code}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-soft">{item.category}</td>
                  <td className="tnum px-4 py-3 text-right">{fmtNumber(item.price, 3)}</td>
                  <td className={`tnum px-4 py-3 text-right ${trendClass(item.change_pct)}`}>
                    {fmtPct(item.change_pct)}
                  </td>
                  <td className="tnum px-4 py-3 text-right text-ink-soft">
                    {item.ma20 === null ? "—" : fmtNumber(item.ma20, 3)}
                  </td>
                  <td className="tnum px-4 py-3 text-right text-ink-soft">
                    {item.aum === null ? "—" : `${fmtNumber(item.aum, 1)} 亿`}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => onRemove(item.code)}
                      className="text-xs text-loss hover:underline"
                    >
                      移除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {items.length === 0 ? (
          <div className="px-4 py-16 text-center">
            <p className="text-sm text-muted">还没有自选 ETF。</p>
            <Link
              href="/etf"
              className="mt-3 inline-block text-sm text-jade-deep hover:underline"
            >
              去 ETF 列表挑几只
            </Link>
          </div>
        ) : null}
      </section>

      <section className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-medium text-ink">自选个股</h2>
          <span className="text-xs text-muted">{stocks.length} 只</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">名称</th>
                <th className="px-4 py-3 font-medium">行业</th>
                <th className="px-4 py-3 text-right font-medium">最新价</th>
                <th className="px-4 py-3 text-right font-medium">日涨跌</th>
                <th className="px-4 py-3 text-right font-medium">股息率 TTM</th>
                <th className="px-4 py-3 text-right font-medium">市值</th>
                <th className="px-4 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((item) => (
                <tr key={item.code} className="border-b border-line/60">
                  <td className="px-4 py-3">
                    <Link
                      href={`/stocks/${item.code}`}
                      className="font-medium text-ink hover:text-jade-deep"
                    >
                      {item.name}
                    </Link>
                    <p className="tnum mt-0.5 text-[11px] text-muted">{item.code}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-soft">
                    {item.industry ?? "未分类"}
                  </td>
                  <td className="tnum px-4 py-3 text-right">
                    {item.price == null ? "—" : item.price.toFixed(2)}
                  </td>
                  <td
                    className={`tnum px-4 py-3 text-right ${
                      item.change_pct == null ? "text-muted" : trendClass(item.change_pct)
                    }`}
                  >
                    {item.change_pct == null ? "—" : fmtPct(item.change_pct)}
                  </td>
                  <td className="tnum px-4 py-3 text-right font-medium text-jade-deep">
                    {item.dividend_yield_ttm == null
                      ? "—"
                      : `${item.dividend_yield_ttm.toFixed(2)}%`}
                  </td>
                  <td className="tnum px-4 py-3 text-right text-ink-soft">
                    {item.market_cap == null ? "—" : `${fmtNumber(item.market_cap, 0)} 亿`}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => onRemoveStock(item.code)}
                      className="text-xs text-loss hover:underline"
                    >
                      移除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {stocks.length === 0 ? (
          <div className="px-4 py-12 text-center">
            <p className="text-sm text-muted">还没有自选个股。</p>
            <Link
              href="/stocks"
              className="mt-3 inline-block text-sm text-jade-deep hover:underline"
            >
              去高股息列表挑几只
            </Link>
          </div>
        ) : null}
      </section>
    </div>
  );
}
