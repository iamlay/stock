"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  adminListStocks,
  adminSyncStock,
  adminUpdateStockStatus,
  fetchMe,
  getToken,
  type AdminStock,
  type Me,
} from "@/lib/auth";

const PAGE_SIZE = 20;

export default function AdminStocksPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [items, setItems] = useState<AdminStock[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    fetchMe()
      .then((user) => {
        if (user.role !== "admin") {
          setError("需要管理员权限");
          return;
        }
        setMe(user);
      })
      .catch(() => setError("登录状态已失效"))
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    if (!me) return;
    setLoading(true);
    adminListStocks({ q: q || undefined, page })
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [me, page, q]);

  async function onToggle(stock: AdminStock) {
    setBusy(stock.code);
    setError(null);
    try {
      const next = stock.status === "excluded" ? "active" : "excluded";
      const updated = await adminUpdateStockStatus(stock.code, next);
      setItems((current) =>
        current.map((item) => (item.code === stock.code ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusy(null);
    }
  }

  async function onSync(stock: AdminStock) {
    setBusy(stock.code);
    setError(null);
    try {
      const updated = await adminSyncStock(stock.code);
      setItems((current) =>
        current.map((item) => (item.code === stock.code ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步失败");
    } finally {
      setBusy(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">个股管理</h1>
          <p className="mt-1 text-sm text-muted">
            启用/停用个股，手动同步分红与行情。
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <Link href="/admin/orders" className="text-jade-deep hover:underline">
            订单
          </Link>
          <Link href="/admin/redeem-codes" className="text-jade-deep hover:underline">
            兑换码
          </Link>
          <Link href="/admin/users" className="text-jade-deep hover:underline">
            用户
          </Link>
        </div>
      </div>

      <form
        className="flex flex-wrap gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
        }}
      >
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="代码或名称"
          className="rounded-sm border border-line bg-surface px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper"
        >
          搜索
        </button>
      </form>

      {error ? <p className="text-sm text-loss">{error}</p> : null}
      {loading ? <p className="text-sm text-muted">加载中…</p> : null}

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-[#faf9f5] text-xs text-muted">
            <tr>
              <th className="px-4 py-3 font-normal">代码 / 名称</th>
              <th className="px-4 py-3 font-normal">行业</th>
              <th className="px-4 py-3 text-right font-normal">TTM 股息率</th>
              <th className="px-4 py-3 text-right font-normal">市值</th>
              <th className="px-4 py-3 font-normal">状态</th>
              <th className="px-4 py-3 text-right font-normal">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {items.map((stock) => (
              <tr key={stock.code}>
                <td className="px-4 py-3">
                  <Link href={`/stocks/${stock.code}`} className="text-ink hover:text-jade-deep">
                    <span className="tnum mr-2 text-xs text-muted">{stock.code}</span>
                    {stock.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-xs text-ink-soft">
                  {stock.industry ?? "未分类"}
                </td>
                <td className="tnum px-4 py-3 text-right text-jade-deep">
                  {stock.dividend_yield_ttm == null
                    ? "—"
                    : `${stock.dividend_yield_ttm.toFixed(2)}%`}
                </td>
                <td className="tnum px-4 py-3 text-right text-xs text-muted">
                  {stock.market_cap == null ? "—" : `${stock.market_cap.toFixed(0)} 亿`}
                </td>
                <td className="px-4 py-3 text-xs">
                  <span
                    className={
                      stock.status === "excluded" ? "text-loss" : "text-jade-deep"
                    }
                  >
                    {stock.status === "excluded" ? "已停用" : "正常"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onSync(stock)}
                    disabled={busy === stock.code}
                    className="mr-2 text-xs text-jade-deep hover:underline disabled:opacity-50"
                  >
                    同步
                  </button>
                  <button
                    type="button"
                    onClick={() => onToggle(stock)}
                    disabled={busy === stock.code}
                    className="text-xs text-ink-soft hover:underline disabled:opacity-50"
                  >
                    {stock.status === "excluded" ? "启用" : "停用"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && items.length === 0 ? (
          <p className="p-8 text-center text-sm text-muted">暂无个股。</p>
        ) : null}
      </div>

      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          共 {total} 只 · 第 {page} / {totalPages} 页
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            className="rounded-sm border border-line bg-surface px-3 py-1.5 disabled:opacity-40"
          >
            上一页
          </button>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((value) => value + 1)}
            className="rounded-sm border border-line bg-surface px-3 py-1.5 disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
