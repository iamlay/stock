"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  fetchEnrichedStockWatchlist,
  fetchMe,
  fetchWatchlist,
  getToken,
  removeStockWatchlist,
  removeWatchlist,
  type StockWatchlistItem,
} from "@/lib/auth";
import type { ApiEtf } from "@/lib/api";
import { fmtNumber, fmtPct, trendClass } from "@/lib/format";

const PERIOD_LABELS: Record<string, string> = {
  Q1: "一季报",
  H1: "中报",
  Q3: "三季报",
  FY: "年报",
};

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(2)}%`;
}

function BandPill({ value }: { value: string | null }) {
  if (!value) return <span className="text-muted">—</span>;
  const low = value.includes("下轨") || value === "中下";
  return (
    <span
      className={`inline-flex rounded-sm px-1.5 py-0.5 text-[10px] ${
        low ? "bg-jade-soft text-jade-deep" : "bg-amber-soft text-amber"
      }`}
    >
      {value.replace("上轨上方", "上").replace("下轨下方", "下")}
    </span>
  );
}

function RatingPill({ value }: { value: string | null }) {
  if (!value) return null;
  const hot = value === "偏热" || value === "高位";
  return (
    <span
      className={`inline-flex rounded-sm px-1.5 py-0.5 text-[10px] ${
        hot ? "bg-loss/10 text-loss" : "bg-jade-soft text-jade-deep"
      }`}
    >
      {value}
    </span>
  );
}

function getBands(item: StockWatchlistItem) {
  return [
    ["日", item.bollinger_daily],
    ["周", item.bollinger_weekly],
    ["月", item.bollinger_monthly],
  ] as const;
}

export default function WatchlistPage() {
  const router = useRouter();
  const [items, setItems] = useState<ApiEtf[]>([]);
  const [stocks, setStocks] = useState<StockWatchlistItem[]>([]);
  const [etfSort, setEtfSort] = useState("default");
  const [stockSort, setStockSort] = useState("yield");
  const [selectedStocks, setSelectedStocks] = useState<Set<string>>(new Set());
  const [batchBusy, setBatchBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const [etfs, stockItems] = await Promise.all([
      fetchWatchlist(),
      fetchEnrichedStockWatchlist(),
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
      setSelectedStocks((current) => {
        const next = new Set(current);
        next.delete(code);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "移除失败");
    }
  }

  const sortedItems = useMemo(() => {
    const copy = [...items];
    if (etfSort === "change") copy.sort((a, b) => b.change_pct - a.change_pct);
    if (etfSort === "aum") copy.sort((a, b) => (b.aum ?? 0) - (a.aum ?? 0));
    if (etfSort === "name") copy.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    return copy;
  }, [items, etfSort]);

  const sortedStocks = useMemo(() => {
    const copy = [...stocks];
    if (stockSort === "yield") {
      copy.sort(
        (a, b) => (b.dividend_yield_ttm ?? -1) - (a.dividend_yield_ttm ?? -1),
      );
    }
    if (stockSort === "cap") copy.sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0));
    if (stockSort === "name") copy.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    return copy;
  }, [stocks, stockSort]);

  function toggleStock(code: string) {
    setSelectedStocks((current) => {
      const next = new Set(current);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function toggleAllStocks() {
    setSelectedStocks((current) =>
      current.size === sortedStocks.length
        ? new Set()
        : new Set(sortedStocks.map((item) => item.code)),
    );
  }

  async function onRemoveSelected() {
    if (selectedStocks.size === 0) return;
    setBatchBusy(true);
    setError(null);
    try {
      await Promise.all([...selectedStocks].map((code) => removeStockWatchlist(code)));
      setStocks((current) => current.filter((item) => !selectedStocks.has(item.code)));
      setSelectedStocks(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量移除失败");
    } finally {
      setBatchBusy(false);
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
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-medium text-ink">自选 ETF</h2>
          <select
            value={etfSort}
            onChange={(event) => setEtfSort(event.target.value)}
            className="rounded-sm border border-line bg-surface px-2 py-1 text-xs text-ink-soft"
          >
            <option value="default">默认顺序</option>
            <option value="change">按日涨跌</option>
            <option value="aum">按规模</option>
            <option value="name">按名称</option>
          </select>
        </div>
        <div className="divide-y divide-line md:hidden">
          {sortedItems.map((item) => (
            <div key={item.code} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <Link
                    href={`/etf/${item.code}`}
                    className="font-medium text-ink hover:text-jade-deep"
                  >
                    {item.name}
                  </Link>
                  <p className="tnum mt-0.5 text-[11px] text-muted">
                    {item.code} · {item.category}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onRemove(item.code)}
                  className="text-xs text-loss hover:underline"
                >
                  移除
                </button>
              </div>
              <div className="mt-2 flex items-baseline gap-3 text-sm">
                <span className="tnum text-ink">{fmtNumber(item.price, 3)}</span>
                <span className={`tnum text-xs ${trendClass(item.change_pct)}`}>
                  {fmtPct(item.change_pct)}
                </span>
                <span className="text-xs text-muted">
                  规模 {item.aum == null ? "—" : `${fmtNumber(item.aum, 1)} 亿`}
                </span>
              </div>
            </div>
          ))}
        </div>
        <div className="hidden overflow-x-auto md:block">
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
              {sortedItems.map((item) => (
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
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
          <h2 className="text-sm font-medium text-ink">自选个股</h2>
          <div className="flex items-center gap-2">
            {selectedStocks.size > 0 ? (
              <button
                type="button"
                onClick={onRemoveSelected}
                disabled={batchBusy}
                className="text-xs text-loss hover:underline disabled:opacity-50"
              >
                {batchBusy ? "移除中…" : `移除选中 ${selectedStocks.size} 只`}
              </button>
            ) : null}
            <select
              value={stockSort}
              onChange={(event) => setStockSort(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-1 text-xs text-ink-soft"
            >
              <option value="yield">按股息率</option>
              <option value="cap">按市值</option>
              <option value="name">按名称</option>
            </select>
            <span className="text-xs text-muted">{stocks.length} 只</span>
          </div>
        </div>
        <div className="divide-y divide-line md:hidden">
          {sortedStocks.map((item) => (
            <div key={item.code} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2">
                  <input
                    type="checkbox"
                    checked={selectedStocks.has(item.code)}
                    onChange={() => toggleStock(item.code)}
                    aria-label={`选择 ${item.name}`}
                    className="mt-1"
                  />
                  <div className="min-w-0">
                    <Link
                      href={`/stocks/${item.code}`}
                      className="block truncate font-medium text-ink hover:text-jade-deep"
                    >
                      {item.name}
                    </Link>
                    <p className="tnum mt-0.5 text-[11px] text-muted">
                      {item.code} · {item.industry ?? "未分类"}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onRemoveStock(item.code)}
                  className="text-xs text-loss hover:underline"
                >
                  移除
                </button>
              </div>

              <div className="mt-2 flex items-end justify-between gap-3">
                <div className="flex items-baseline gap-2">
                  <span className="tnum text-sm text-ink">
                    {item.price == null ? "—" : item.price.toFixed(2)}
                  </span>
                  <span
                    className={`tnum text-xs ${
                      item.change_pct == null ? "text-muted" : trendClass(item.change_pct)
                    }`}
                  >
                    {item.change_pct == null ? "—" : fmtPct(item.change_pct)}
                  </span>
                </div>
                <div className="text-right">
                  <p className="tnum text-lg font-semibold text-jade-deep">
                    {pct(item.dividend_yield_ttm)}
                  </p>
                  <p className="text-[10px] text-muted">
                    静态 {pct(item.dividend_yield_fy)}
                  </p>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] text-muted">BOLL</span>
                {getBands(item).map(([label, band]) => (
                  <span key={label} className="inline-flex items-center gap-1">
                    <span className="text-[10px] text-muted">{label}</span>
                    <BandPill value={band?.position ?? null} />
                  </span>
                ))}
                <RatingPill value={item.bollinger_rating} />
              </div>

              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted">
                <span>
                  {item.latest_financial
                    ? `${PERIOD_LABELS[item.latest_financial.period] ?? item.latest_financial.period} · 披露 ${item.latest_financial.disclosure_date ?? "—"}`
                    : "财务披露 —"}
                </span>
                <span>
                  {item.grid_targets.length > 0
                    ? item.grid_targets
                        .map(
                          (target) =>
                            `${target.target_yield}% ${target.target_price.toFixed(2)}`,
                        )
                        .join(" / ")
                    : "网格 —"}
                </span>
              </div>
            </div>
          ))}
        </div>
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1280px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={
                      sortedStocks.length > 0 &&
                      selectedStocks.size === sortedStocks.length
                    }
                    onChange={toggleAllStocks}
                    aria-label="全选"
                  />
                </th>
                <th className="px-4 py-3 font-medium">名称</th>
                <th className="px-4 py-3 font-medium">行业</th>
                <th className="px-4 py-3 text-right font-medium">最新价</th>
                <th className="px-4 py-3 text-right font-medium">日涨跌</th>
                <th className="px-4 py-3 text-right font-medium">TTM</th>
                <th className="px-4 py-3 text-right font-medium">静态</th>
                <th className="px-4 py-3 font-medium">BOLL 日/周/月</th>
                <th className="px-4 py-3 font-medium">评级</th>
                <th className="px-4 py-3 text-right font-medium">披露</th>
                <th className="px-4 py-3 text-right font-medium">网格 5/5.5/6%</th>
                <th className="px-4 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {sortedStocks.map((item) => (
                <tr key={item.code} className="border-b border-line/60">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedStocks.has(item.code)}
                      onChange={() => toggleStock(item.code)}
                      aria-label={`选择 ${item.name}`}
                    />
                  </td>
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
                    {pct(item.dividend_yield_ttm)}
                  </td>
                  <td className="tnum px-4 py-3 text-right text-ink-soft">
                    {pct(item.dividend_yield_fy)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {getBands(item).map(([label, band]) => (
                        <span key={label} className="inline-flex items-center gap-1">
                          <span className="text-[10px] text-muted">{label}</span>
                          <BandPill value={band?.position ?? null} />
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <RatingPill value={item.bollinger_rating} />
                  </td>
                  <td className="tnum px-4 py-3 text-right text-xs text-muted">
                    {item.latest_financial?.disclosure_date ?? "—"}
                  </td>
                  <td className="tnum px-4 py-3 text-right text-[11px] text-muted">
                    {item.grid_targets.length === 0
                      ? "—"
                      : item.grid_targets
                          .map((target) => target.target_price.toFixed(2))
                          .join(" / ")}
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
