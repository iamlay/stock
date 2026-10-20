"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  adminGetUserDetail,
  fetchMe,
  getToken,
  type AdminUserDetail,
} from "@/lib/auth";

function fmtDate(value: string | null): string {
  return value ? value.slice(0, 10) : "—";
}

function fmtDateTime(value: string | null): string {
  return value ? value.slice(0, 16).replace("T", " ") : "—";
}

export default function AdminUserDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [data, setData] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!Number.isFinite(id)) {
      setError("用户 ID 无效");
      setLoading(false);
      return;
    }
    fetchMe()
      .then(async (profile) => {
        if (profile.role !== "admin") {
          setForbidden(true);
          return;
        }
        setData(await adminGetUserDetail(id));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [id, router]);

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }
  if (forbidden) {
    return <p className="py-20 text-center text-sm text-muted">需要管理员权限。</p>;
  }
  if (!data) {
    return (
      <div className="py-20 text-center">
        <p className="text-sm text-loss">{error ?? "用户不存在"}</p>
        <Link href="/admin/users" className="mt-3 inline-block text-sm text-jade-deep hover:underline">
          返回用户列表
        </Link>
      </div>
    );
  }

  const { user, orders, codes, backtests } = data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/admin/users" className="text-xs text-muted hover:text-ink">
            ← 返回用户列表
          </Link>
          <h1 className="mt-2 break-all font-serif text-3xl text-ink">
            {user.email ?? user.phone ?? `用户 #${user.id}`}
          </h1>
          <p className="mt-1 text-sm text-muted">用户 #{user.id} 的订单、兑换码与回测记录</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/admin/orders"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            订单流水
          </Link>
          <Link
            href="/admin/redeem-codes"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            兑换码管理
          </Link>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-4">
        {[
          ["角色", user.role === "admin" ? "管理员" : "用户"],
          ["套餐", user.plan === "member" ? "会员" : "免费"],
          ["到期", user.plan === "member" ? fmtDate(user.plan_expires_at) : "—"],
          ["状态", user.status === "banned" ? "已封禁" : "正常"],
        ].map(([label, value]) => (
          <div key={label} className="card p-4">
            <p className="text-xs text-muted">{label}</p>
            <p className="mt-2 text-base font-medium text-ink">{value}</p>
          </div>
        ))}
      </section>

      <section className="card p-5">
        <h2 className="text-base font-medium text-ink">账号信息</h2>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-muted">邮箱</dt>
            <dd className="mt-1 break-all">{user.email ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">手机号</dt>
            <dd className="mt-1">{user.phone ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">邮箱验证</dt>
            <dd className="mt-1">
              {user.email ? (user.email_verified ? "已验证" : "未验证") : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">注册时间</dt>
            <dd className="mt-1">{fmtDateTime(user.created_at)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">最近登录</dt>
            <dd className="mt-1">{fmtDateTime(user.last_login_at)}</dd>
          </div>
        </dl>
      </section>

      <section className="card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium text-ink">订单</h2>
          <span className="text-xs text-muted">最近 {orders.length} 条</span>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 pr-3 font-medium">订单号</th>
                <th className="py-2 pr-3 font-medium">平台</th>
                <th className="py-2 pr-3 text-right font-medium">金额</th>
                <th className="py-2 pr-3 font-medium">状态</th>
                <th className="py-2 pr-3 font-medium">兑换码</th>
                <th className="py-2 font-medium">时间</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id} className="border-b border-line/60">
                  <td className="tnum py-2 pr-3 text-xs">{order.order_no}</td>
                  <td className="py-2 pr-3 text-xs">{order.platform}</td>
                  <td className="tnum py-2 pr-3 text-right">¥{order.amount.toFixed(2)}</td>
                  <td className="py-2 pr-3 text-xs">
                    {order.status === "refunded" ? "已退款" : "已交付"}
                  </td>
                  <td className="tnum py-2 pr-3 font-mono text-xs text-muted">
                    {order.code ?? "—"}
                  </td>
                  <td className="py-2 text-xs text-muted">{fmtDate(order.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {orders.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">暂无订单</p>
        ) : null}
      </section>

      <section className="card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium text-ink">兑换码</h2>
          <span className="text-xs text-muted">最近 {codes.length} 条</span>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 pr-3 font-medium">兑换码</th>
                <th className="py-2 pr-3 font-medium">套餐</th>
                <th className="py-2 pr-3 font-medium">天数</th>
                <th className="py-2 pr-3 font-medium">状态</th>
                <th className="py-2 pr-3 font-medium">有效期</th>
                <th className="py-2 font-medium">兑换时间</th>
              </tr>
            </thead>
            <tbody>
              {codes.map((code) => (
                <tr key={code.code} className="border-b border-line/60">
                  <td className="tnum py-2 pr-3 font-mono text-xs">{code.code}</td>
                  <td className="py-2 pr-3 text-xs">{code.plan === "member" ? "会员" : "试用"}</td>
                  <td className="tnum py-2 pr-3 text-xs">{code.duration_days}</td>
                  <td className="py-2 pr-3 text-xs">
                    {code.status === "issued"
                      ? "未使用"
                      : code.status === "redeemed"
                        ? "已兑换"
                        : code.status === "revoked"
                          ? "已作废"
                          : "已过期"}
                  </td>
                  <td className="tnum py-2 pr-3 text-xs text-muted">
                    {fmtDate(code.expires_at)}
                  </td>
                  <td className="py-2 text-xs text-muted">{fmtDate(code.redeemed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {codes.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">暂无兑换码</p>
        ) : null}
      </section>

      <section className="card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium text-ink">回测历史</h2>
          <span className="text-xs text-muted">最近 {backtests.length} 条</span>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 pr-3 font-medium">策略</th>
                <th className="py-2 pr-3 font-medium">标的</th>
                <th className="py-2 pr-3 text-right font-medium">累计收益</th>
                <th className="py-2 pr-3 text-right font-medium">交易数</th>
                <th className="py-2 pr-3 font-medium">状态</th>
                <th className="py-2 font-medium">时间</th>
              </tr>
            </thead>
            <tbody>
              {backtests.map((run) => (
                <tr key={run.id} className="border-b border-line/60">
                  <td className="py-2 pr-3 text-xs">{run.strategy}</td>
                  <td className="tnum py-2 pr-3 font-mono text-xs">{run.code}</td>
                  <td
                    className={`tnum py-2 pr-3 text-right text-xs ${
                      run.total_return >= 0 ? "text-gain" : "text-loss"
                    }`}
                  >
                    {run.total_return >= 0 ? "+" : ""}
                    {run.total_return.toFixed(2)}%
                  </td>
                  <td className="tnum py-2 pr-3 text-right text-xs">{run.trades}</td>
                  <td className="py-2 pr-3 text-xs">{run.status}</td>
                  <td className="py-2 text-xs text-muted">{fmtDateTime(run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {backtests.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">暂无回测记录</p>
        ) : null}
      </section>
    </div>
  );
}
