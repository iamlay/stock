"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  adminCreateOrder,
  adminListOrders,
  adminRefundOrder,
  fetchMe,
  getToken,
  type AdminOrder,
  type Me,
} from "@/lib/auth";

const PAGE_SIZE = 10;

const STATUS_LABELS: Record<string, string> = {
  delivered: "已交付",
  refunded: "已退款",
  pending: "待支付",
};

export default function AdminOrdersPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [items, setItems] = useState<AdminOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [revenue, setRevenue] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [search, setSearch] = useState("");

  const [platform, setPlatform] = useState("zhishixingqiu");
  const [externalId, setExternalId] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState(199);
  const [days, setDays] = useState(365);
  const [product, setProduct] = useState("member-365");
  const [note, setNote] = useState("");
  const [createdCode, setCreatedCode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(
    targetPage = 1,
    nextStatus = statusFilter,
    nextPlatform = platformFilter,
    nextSearch = search,
  ) {
    const data = await adminListOrders({
      status: nextStatus || undefined,
      platform: nextPlatform || undefined,
      q: nextSearch || undefined,
      page: targetPage,
      page_size: PAGE_SIZE,
    });
    setItems(data.items);
    setTotal(data.total);
    setRevenue(data.revenue);
    setPage(data.page);
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    fetchMe()
      .then(async (profile) => {
        if (profile.role !== "admin") {
          setForbidden(true);
          return;
        }
        setMe(profile);
        await load(1);
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function onCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setCreatedCode(null);
    try {
      const order = await adminCreateOrder({
        platform,
        external_order_id: externalId || undefined,
        buyer_phone: phone || undefined,
        amount,
        days,
        plan: "member",
        product,
        note: note || undefined,
      });
      setCreatedCode(order.code);
      setMessage(`订单 ${order.order_no} 已登记，兑换码 ${order.code}`);
      setExternalId("");
      setPhone("");
      setNote("");
      await load(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登记失败");
    }
  }

  async function onRefund(orderNo: string) {
    setError(null);
    try {
      await adminRefundOrder(orderNo);
      setMessage(`订单 ${orderNo} 已退款，未使用的兑换码已作废`);
      await load(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "退款失败");
    }
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }
  if (forbidden) {
    return <p className="py-20 text-center text-sm text-muted">需要管理员权限。</p>;
  }
  if (!me) return null;

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">订单流水</h1>
          <p className="mt-1 text-sm text-muted">第三方平台订单登记、发码与退款</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/admin/redeem-codes"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            兑换码管理
          </Link>
          <Link
            href="/account"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft hover:border-ink"
          >
            个人中心
          </Link>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="card p-4">
          <p className="text-xs text-muted">订单数</p>
          <p className="tnum mt-2 text-xl font-semibold text-ink">{total}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">已交付收入</p>
          <p className="tnum mt-2 text-xl font-semibold text-ink">¥{revenue.toFixed(2)}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-muted">客单价</p>
          <p className="tnum mt-2 text-xl font-semibold text-ink">
            ¥{total ? (revenue / total).toFixed(2) : "0.00"}
          </p>
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-base font-medium text-ink">登记订单并自动发码</h2>
        <form onSubmit={onCreate} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex w-32 flex-col gap-1">
            <span className="text-xs text-muted">平台</span>
            <select
              value={platform}
              onChange={(event) => setPlatform(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            >
              <option value="zhishixingqiu">知识星球</option>
              <option value="xiaoe">小鹅通</option>
              <option value="manual">手动</option>
            </select>
          </label>
          <label className="flex w-40 flex-col gap-1">
            <span className="text-xs text-muted">外部订单号</span>
            <input
              value={externalId}
              onChange={(event) => setExternalId(event.target.value)}
              placeholder="平台订单号"
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-32 flex-col gap-1">
            <span className="text-xs text-muted">买家手机号</span>
            <input
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="选填"
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-24 flex-col gap-1">
            <span className="text-xs text-muted">金额</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(Number(event.target.value))}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-24 flex-col gap-1">
            <span className="text-xs text-muted">会员天数</span>
            <input
              type="number"
              min={1}
              max={3650}
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-32 flex-col gap-1">
            <span className="text-xs text-muted">产品</span>
            <input
              value={product}
              onChange={(event) => setProduct(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <button
            type="submit"
            className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep"
          >
            登记并发码
          </button>
        </form>

        {message ? <p className="mt-3 text-xs text-jade-deep">{message}</p> : null}
        {error ? <p className="mt-3 text-xs text-loss">{error}</p> : null}
        {createdCode ? (
          <p className="tnum mt-2 font-mono text-xs text-ink">兑换码：{createdCode}</p>
        ) : null}
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto text-base font-medium text-ink">订单列表</h2>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") load(1, statusFilter, platformFilter, search);
            }}
            placeholder="订单号 / 手机号"
            className="w-40 rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          />
          <select
            value={platformFilter}
            onChange={(event) => {
              setPlatformFilter(event.target.value);
              load(1, statusFilter, event.target.value, search);
            }}
            className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">全部平台</option>
            <option value="zhishixingqiu">知识星球</option>
            <option value="xiaoe">小鹅通</option>
            <option value="manual">手动</option>
          </select>
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              load(1, event.target.value, platformFilter, search);
            }}
            className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">全部状态</option>
            <option value="delivered">已交付</option>
            <option value="refunded">已退款</option>
          </select>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 font-medium">订单号</th>
                <th className="py-2 font-medium">平台</th>
                <th className="py-2 font-medium">外部单号</th>
                <th className="py-2 font-medium">买家</th>
                <th className="py-2 text-right font-medium">金额</th>
                <th className="py-2 font-medium">状态</th>
                <th className="py-2 font-medium">兑换码</th>
                <th className="py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((order) => (
                <tr key={order.id} className="border-b border-line/60">
                  <td className="tnum py-2 text-xs">{order.order_no}</td>
                  <td className="py-2 text-xs">{order.platform}</td>
                  <td className="py-2 text-xs text-muted">{order.external_order_id ?? "—"}</td>
                  <td className="py-2 text-xs">{order.buyer_phone ?? "—"}</td>
                  <td className="tnum py-2 text-right">¥{order.amount.toFixed(2)}</td>
                  <td className="py-2">
                    <span
                      className={`inline-flex rounded-sm px-1.5 py-0.5 text-[11px] ${
                        order.status === "refunded"
                          ? "bg-[#f8ece9] text-[#9a3f2c]"
                          : "bg-jade-soft text-jade-deep"
                      }`}
                    >
                      {STATUS_LABELS[order.status] ?? order.status}
                    </span>
                  </td>
                  <td className="tnum py-2 font-mono text-xs text-muted">{order.code ?? "—"}</td>
                  <td className="py-2 text-right">
                    {order.status !== "refunded" ? (
                      <button
                        type="button"
                        onClick={() => onRefund(order.order_no)}
                        className="text-xs text-loss hover:underline"
                      >
                        退款
                      </button>
                    ) : (
                      <span className="text-xs text-muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex items-center justify-between text-xs text-muted">
          <span>
            共 {total} 条 · 第 {page}/{pages} 页
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => load(page - 1)}
              className="rounded-sm border border-line px-2 py-1 disabled:opacity-40"
            >
              上一页
            </button>
            <button
              type="button"
              disabled={page >= pages}
              onClick={() => load(page + 1)}
              className="rounded-sm border border-line px-2 py-1 disabled:opacity-40"
            >
              下一页
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
