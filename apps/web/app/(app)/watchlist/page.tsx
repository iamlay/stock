"use client";

import { UpgradePrompt } from "@/components/upgrade-prompt";
import { readWatchlistFilters, watchlistTaskPath, type WatchlistFilters } from "@/lib/task-context";
import { currentReturnPath, withReturnPath } from "@/lib/return-path";

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
  updateEtfWatchlistGroup,
  updateStockWatchlistGroup,
  type StockWatchlistItem,
  type Me,
} from "@/lib/auth";
import type { ApiEtf } from "@/lib/api";
import { fmtNumber, fmtPct, trendClass } from "@/lib/format";

const PERIOD_LABELS: Record<string, string> = {
  Q1: "一季报",
  H1: "中报",
  Q3: "三季报",
  FY: "年报",
};

const WATCHLIST_PREFS_KEY = "stocklab.watchlist.prefs";

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

function percentileLabel(value: number | null): string | null {
  if (value == null) return null;
  if (value >= 80) return "10年高位";
  if (value <= 20) return "10年低位";
  return "10年中位";
}

function getBands(item: StockWatchlistItem) {
  return [
    ["日", item.bollinger_daily],
    ["周", item.bollinger_weekly],
    ["月", item.bollinger_monthly],
  ] as const;
}

function bandRank(position: string | null | undefined): number {
  if (position === "下轨下方") return 0;
  if (position === "中下") return 1;
  if (position === "中上") return 2;
  if (position === "上轨上方") return 3;
  return 9;
}

function lowBand(position: string | null | undefined): boolean {
  return position === "中下" || position === "下轨下方";
}

function isResonance(item: StockWatchlistItem): boolean {
  return (
    lowBand(item.bollinger_weekly?.position) &&
    lowBand(item.bollinger_monthly?.position)
  );
}

function isLowValue(item: StockWatchlistItem): boolean {
  return (item.yield_percentile ?? -1) >= 80;
}

function GroupSelect({
  scope,
  code,
  value,
  groups,
  onChanged,
}: {
  scope: "stock" | "etf";
  code: string;
  value: string;
  groups: string[];
  onChanged: (group: string) => void;
}) {
  const options = groups.includes(value) ? groups : [...groups, value];
  return (
    <select
      value={value}
      onChange={async (event) => {
        let next = event.target.value;
        if (next === "__new") {
          const name = window.prompt("新分组名称（最多 20 字）")?.trim();
          if (!name) return;
          next = name.slice(0, 20);
        }
        if (next === value) return;
        try {
          if (scope === "stock") {
            await updateStockWatchlistGroup(code, next);
          } else {
            await updateEtfWatchlistGroup(code, next);
          }
          onChanged(next);
        } catch (err) {
          window.alert(err instanceof Error ? err.message : "修改分组失败");
        }
      }}
      className="max-w-28 rounded-sm border border-line bg-surface px-1.5 py-1 text-[11px] text-ink-soft"
      aria-label="自选分组"
    >
      {options.map((group) => (
        <option key={group} value={group}>
          {group}
        </option>
      ))}
      <option value="__new">+ 新建分组</option>
    </select>
  );
}

function csvCell(value: string | number | null | undefined): string {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function exportWatchlistCsv(items: StockWatchlistItem[]): void {
  const header = [
    "分组",
    "代码",
    "名称",
    "行业",
    "现价",
    "涨跌幅%",
    "TTM股息率%",
    "RLY%",
    "静态股息率%",
    "10年分位%",
    "日BOLL",
    "周BOLL",
    "月BOLL",
    "评级",
    "最新报告",
    "披露日",
    "网格5%",
    "网格5.5%",
    "网格6%",
  ];
  const rows = items.map((item) => {
    const financial = item.latest_financial;
    const targets = item.grid_targets;
    return [
      item.group_name || "默认",
      item.code,
      item.name,
      item.industry,
      item.price,
      item.change_pct,
      item.dividend_yield_ttm,
      item.dividend_yield_ly,
      item.dividend_yield_fy,
      item.yield_percentile,
      item.bollinger_daily?.position,
      item.bollinger_weekly?.position,
      item.bollinger_monthly?.position,
      item.bollinger_rating,
      financial?.period,
      financial?.disclosure_date,
      targets[0]?.target_price,
      targets[1]?.target_price,
      targets[2]?.target_price,
    ].map(csvCell);
  });
  const csv = `\uFEFF${[header.map(csvCell), ...rows].map((row) => row.join(",")).join("\r\n")}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `stocklab-watchlist-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function WatchlistPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [items, setItems] = useState<ApiEtf[]>([]);
  const [stocks, setStocks] = useState<StockWatchlistItem[]>([]);
  const [etfSort, setEtfSort] = useState("default");
  const [stockSort, setStockSort] = useState("yield");
  const [onlyResonance, setOnlyResonance] = useState(false);
  const [onlyLowValue, setOnlyLowValue] = useState(false);
  const [etfGroup, setEtfGroup] = useState("全部");
  const [stockGroup, setStockGroup] = useState("全部");
  const [prefsReady, setPrefsReady] = useState(false);
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
      router.replace(withReturnPath("/login", currentReturnPath()));
      return;
    }
    fetchMe()
      .then((profile) => { setMe(profile); return load(); })
      .catch(() => router.replace(withReturnPath("/login", currentReturnPath())))
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    let saved: Partial<WatchlistFilters> = {};
    try {
      const raw = window.localStorage.getItem(WATCHLIST_PREFS_KEY);
      if (raw) saved = JSON.parse(raw) ?? {};
    } catch {
      // URL context still restores the task when local preferences are unavailable.
    }
    saved = { ...saved, ...readWatchlistFilters(new URLSearchParams(window.location.search)) };
    if (saved.etfSort) setEtfSort(saved.etfSort);
    if (saved.stockSort) setStockSort(saved.stockSort);
    setOnlyResonance(Boolean(saved.onlyResonance));
    setOnlyLowValue(Boolean(saved.onlyLowValue));
    if (saved.etfGroup) setEtfGroup(saved.etfGroup);
    if (saved.stockGroup) setStockGroup(saved.stockGroup);
    setPrefsReady(true);
  }, []);

  useEffect(() => {
    if (!prefsReady) return;
    window.localStorage.setItem(
      WATCHLIST_PREFS_KEY,
      JSON.stringify({
        etfSort,
        stockSort,
        onlyResonance,
        onlyLowValue,
        etfGroup,
        stockGroup,
      }),
    );
  }, [
    etfSort,
    stockSort,
    onlyResonance,
    onlyLowValue,
    etfGroup,
    stockGroup,
    prefsReady,
  ]);

  useEffect(() => {
    if (!getToken()) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        load().catch(() => undefined);
      }
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

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

  const etfGroups = useMemo(
    () => ["全部", ...new Set(items.map((item) => item.group_name || "默认"))],
    [items],
  );
  const stockGroups = useMemo(
    () => ["全部", ...new Set(stocks.map((item) => item.group_name || "默认"))],
    [stocks],
  );

  useEffect(() => {
    if (etfGroup !== "全部" && !etfGroups.includes(etfGroup)) setEtfGroup("全部");
  }, [etfGroup, etfGroups]);

  useEffect(() => {
    if (stockGroup !== "全部" && !stockGroups.includes(stockGroup)) {
      setStockGroup("全部");
    }
  }, [stockGroup, stockGroups]);

  const sortedItems = useMemo(() => {
    const copy = items.filter(
      (item) => etfGroup === "全部" || (item.group_name || "默认") === etfGroup,
    );
    if (etfSort === "change") copy.sort((a, b) => b.change_pct - a.change_pct);
    if (etfSort === "aum") copy.sort((a, b) => (b.aum ?? 0) - (a.aum ?? 0));
    if (etfSort === "name") copy.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    return copy;
  }, [items, etfSort, etfGroup]);

  const visibleStocks = useMemo(
    () =>
      stocks.filter(
        (item) =>
          (stockGroup === "全部" || (item.group_name || "默认") === stockGroup) &&
          (!onlyResonance || isResonance(item)) &&
          (!onlyLowValue || isLowValue(item)),
      ),
    [stocks, onlyResonance, onlyLowValue, stockGroup],
  );

  const sortedStocks = useMemo(() => {
    const copy = [...visibleStocks];
    if (stockSort === "yield") {
      copy.sort(
        (a, b) => (b.dividend_yield_ttm ?? -1) - (a.dividend_yield_ttm ?? -1),
      );
    }
    if (stockSort === "rly") {
      copy.sort(
        (a, b) => (b.dividend_yield_ly ?? -1) - (a.dividend_yield_ly ?? -1),
      );
    }
    if (stockSort === "percentile") {
      copy.sort(
        (a, b) => (b.yield_percentile ?? -1) - (a.yield_percentile ?? -1),
      );
    }
    if (stockSort === "bollinger") {
      copy.sort(
        (a, b) =>
          bandRank(a.bollinger_weekly?.position) +
          bandRank(a.bollinger_monthly?.position) -
          (bandRank(b.bollinger_weekly?.position) +
            bandRank(b.bollinger_monthly?.position)),
      );
    }
    if (stockSort === "cap") copy.sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0));
    if (stockSort === "name") copy.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    return copy;
  }, [visibleStocks, stockSort]);

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

      <p className="text-sm text-muted">自选合计 {items.length + stocks.length} 个（股票 + ETF）。{me?.entitlements.capabilities.unlimited_watchlist ? "当前权益不限数量。" : "免费账号最多 10 个，到期不删除已有自选。"}</p>
      {me && !me.entitlements.capabilities.unlimited_watchlist && items.length + stocks.length >= 10 ? <UpgradePrompt
        scene="watchlist" profile={me}
        returnPath={watchlistTaskPath({ etfSort, stockSort, etfGroup, stockGroup, onlyResonance, onlyLowValue })}
      /> : null}
      {error ? <p className="text-xs text-loss">{error}</p> : null}

      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
          <h2 className="text-sm font-medium text-ink">自选 ETF</h2>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={etfGroup}
              onChange={(event) => setEtfGroup(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-1 text-xs text-ink-soft"
            >
              {etfGroups.map((group) => (
                <option key={group} value={group}>
                  {group === "全部" ? "全部分组" : group}
                </option>
              ))}
            </select>
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
            <span className="text-xs text-muted">{sortedItems.length} 只</span>
          </div>
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
              <div className="mt-2">
                <GroupSelect
                  scope="etf"
                  code={item.code}
                  value={item.group_name || "默认"}
                  groups={etfGroups.filter((group) => group !== "全部")}
                  onChanged={(group) =>
                    setItems((current) =>
                      current.map((row) =>
                        row.code === item.code ? { ...row, group_name: group } : row,
                      ),
                    )
                  }
                />
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
                <th className="px-4 py-3 font-medium">分组</th>
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
                  <td className="px-4 py-3">
                    <GroupSelect
                      scope="etf"
                      code={item.code}
                      value={item.group_name || "默认"}
                      groups={etfGroups.filter((group) => group !== "全部")}
                      onChanged={(group) =>
                        setItems((current) =>
                          current.map((row) =>
                            row.code === item.code ? { ...row, group_name: group } : row,
                          ),
                        )
                      }
                    />
                  </td>
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
          <div className="flex flex-wrap items-center gap-2">
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
            <label className="flex items-center gap-1 text-xs text-ink-soft">
              <input
                type="checkbox"
                checked={onlyResonance}
                onChange={(event) => setOnlyResonance(event.target.checked)}
              />
              低位共振
            </label>
            <label className="flex items-center gap-1 text-xs text-ink-soft">
              <input
                type="checkbox"
                checked={onlyLowValue}
                onChange={(event) => setOnlyLowValue(event.target.checked)}
              />
              低估值
            </label>
            <select
              value={stockGroup}
              onChange={(event) => setStockGroup(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-1 text-xs text-ink-soft"
            >
              {stockGroups.map((group) => (
                <option key={group} value={group}>
                  {group === "全部" ? "全部分组" : group}
                </option>
              ))}
            </select>
            <select
              value={stockSort}
              onChange={(event) => setStockSort(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-1 text-xs text-ink-soft"
            >
              <option value="yield">按 TTM 股息率</option>
              <option value="rly">按 RLY</option>
              <option value="percentile">按 10 年分位</option>
              <option value="bollinger">按 BOLL 低位</option>
              <option value="cap">按市值</option>
              <option value="name">按名称</option>
            </select>
            <button
              type="button"
              onClick={() => exportWatchlistCsv(sortedStocks)}
              className="rounded-sm border border-line bg-surface px-2 py-1 text-xs text-jade-deep hover:border-jade"
            >
              导出 CSV
            </button>
            <span className="text-xs text-muted">
              {sortedStocks.length}/{stocks.length} 只
            </span>
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
                      {item.quote_time
                        ? ` · 更新 ${new Date(item.quote_time).toLocaleTimeString("zh-CN", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}`
                        : ""}
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

              <div className="mt-2">
                <GroupSelect
                  scope="stock"
                  code={item.code}
                  value={item.group_name || "默认"}
                  groups={stockGroups.filter((group) => group !== "全部")}
                  onChanged={(group) =>
                    setStocks((current) =>
                      current.map((row) =>
                        row.code === item.code ? { ...row, group_name: group } : row,
                      ),
                    )
                  }
                />
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
                  <p className="text-[10px] text-muted">
                    RLY {pct(item.dividend_yield_ly)}
                  </p>
                  {item.yield_percentile != null ? (
                    <p className="tnum mt-0.5 text-[10px] text-amber">
                      分位 {item.yield_percentile.toFixed(0)}% ·{" "}
                      {percentileLabel(item.yield_percentile)}
                    </p>
                  ) : null}
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
                {isResonance(item) ? (
                  <span className="rounded-sm bg-jade-soft px-1.5 py-0.5 text-[10px] text-jade-deep">
                    低位共振
                  </span>
                ) : null}
                {isLowValue(item) ? (
                  <span className="rounded-sm bg-amber-soft px-1.5 py-0.5 text-[10px] text-amber">
                    低估值
                  </span>
                ) : null}
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

              <div className="mt-2 flex gap-3 text-[11px]">
                <Link
                  href={`/stocks/${item.code}?tab=grid`}
                  className="text-jade-deep hover:underline"
                >
                  股息网格
                </Link>
                <Link
                  href={`/stocks/${item.code}?tab=bollinger`}
                  className="text-jade-deep hover:underline"
                >
                  布林详情
                </Link>
                <Link
                  href={`/stocks/${item.code}?tab=financial`}
                  className="text-jade-deep hover:underline"
                >
                  财务
                </Link>
              </div>
            </div>
          ))}
        </div>
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[1280px] whitespace-nowrap text-sm">
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
                <th className="px-4 py-3 font-medium">分组</th>
                <th className="px-4 py-3 text-right font-medium">最新价</th>
                <th className="px-4 py-3 text-right font-medium">日涨跌</th>
                <th className="px-4 py-3 text-right font-medium">TTM</th>
                <th className="px-4 py-3 text-right font-medium">RLY</th>
                <th className="px-4 py-3 text-right font-medium">静态</th>
                <th className="px-4 py-3 text-right font-medium">10年分位</th>
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
                  <td className="px-4 py-3">
                    <GroupSelect
                      scope="stock"
                      code={item.code}
                      value={item.group_name || "默认"}
                      groups={stockGroups.filter((group) => group !== "全部")}
                      onChanged={(group) =>
                        setStocks((current) =>
                          current.map((row) =>
                            row.code === item.code ? { ...row, group_name: group } : row,
                          ),
                        )
                      }
                    />
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
                    {pct(item.dividend_yield_ly)}
                  </td>
                  <td className="tnum px-4 py-3 text-right text-ink-soft">
                    {pct(item.dividend_yield_fy)}
                  </td>
                  <td className="tnum px-4 py-3 text-right text-xs text-amber">
                    {item.yield_percentile == null
                      ? "—"
                      : `${item.yield_percentile.toFixed(0)}%`}
                    {item.yield_percentile != null
                      ? ` · ${percentileLabel(item.yield_percentile)}`
                      : ""}
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
                    <div className="flex justify-end gap-2 text-[11px]">
                      <Link
                        href={`/stocks/${item.code}?tab=grid`}
                        className="text-jade-deep hover:underline"
                      >
                        网格
                      </Link>
                      <Link
                        href={`/stocks/${item.code}?tab=bollinger`}
                        className="text-jade-deep hover:underline"
                      >
                        布林
                      </Link>
                      <Link
                        href={`/stocks/${item.code}?tab=financial`}
                        className="text-jade-deep hover:underline"
                      >
                        财务
                      </Link>
                      <button
                        type="button"
                        onClick={() => onRemoveStock(item.code)}
                        className="text-loss hover:underline"
                      >
                        移除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {stocks.length > 0 && sortedStocks.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-muted">
            没有符合当前筛选的自选股。取消“低位共振”或“低估值”后再试。
          </div>
        ) : null}
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
