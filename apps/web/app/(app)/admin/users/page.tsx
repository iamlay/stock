"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  adminListUsers,
  adminUpdateUser,
  fetchMe,
  getToken,
  type AdminUser,
} from "@/lib/auth";

const PAGE_SIZE = 10;

function fmtDate(value: string | null): string {
  return value ? value.slice(0, 10) : "—";
}

export default function AdminUsersPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [days, setDays] = useState(365);
  const [busy, setBusy] = useState(false);

  async function load(
    targetPage = 1,
    nextQuery = query,
    nextPlan = planFilter,
    nextStatus = statusFilter,
  ) {
    const data = await adminListUsers({
      q: nextQuery || undefined,
      plan: nextPlan || undefined,
      status: nextStatus || undefined,
      page: targetPage,
      page_size: PAGE_SIZE,
    });
    setItems(data.items);
    setTotal(data.total);
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
        await load(1);
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function onToggleBan(user: AdminUser) {
    const next = user.status === "banned" ? "active" : "banned";
    if (next === "banned" && !window.confirm(`确认封禁 ${user.email ?? user.phone}？`)) {
      return;
    }
    setError(null);
    setMessage(null);
    try {
      await adminUpdateUser(user.id, { status: next });
      setMessage(next === "banned" ? "已封禁" : "已解封");
      await load(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function onGrant() {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      await adminUpdateUser(editing.id, { plan: "member", days });
      setMessage(`已为 ${editing.email ?? editing.phone} 开通 ${days} 天会员`);
      setEditing(null);
      await load(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "开通失败");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke() {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      await adminUpdateUser(editing.id, { plan: "free" });
      setMessage(`已取消 ${editing.email ?? editing.phone} 的会员`);
      setEditing(null);
      await load(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }
  if (forbidden) {
    return <p className="py-20 text-center text-sm text-muted">需要管理员权限。</p>;
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">用户管理</h1>
          <p className="mt-1 text-sm text-muted">搜索、封禁、调整会员</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/admin/redeem-codes"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            兑换码管理
          </Link>
          <Link
            href="/admin/orders"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            订单流水
          </Link>
        </div>
      </div>

      {message ? <p className="text-xs text-jade-deep">{message}</p> : null}
      {error ? <p className="text-xs text-loss">{error}</p> : null}

      <section className="card p-5">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") load(1, query, planFilter, statusFilter);
            }}
            placeholder="搜索邮箱 / 手机号"
            className="w-56 rounded-sm border border-line bg-surface px-3 py-1.5 text-sm"
          />
          <select
            value={planFilter}
            onChange={(event) => {
              setPlanFilter(event.target.value);
              load(1, query, event.target.value, statusFilter);
            }}
            className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">全部套餐</option>
            <option value="free">免费</option>
            <option value="member">会员</option>
          </select>
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              load(1, query, planFilter, event.target.value);
            }}
            className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">全部状态</option>
            <option value="active">正常</option>
            <option value="banned">已封禁</option>
          </select>
          <button
            type="button"
            onClick={() => load(1, query, planFilter, statusFilter)}
            className="rounded-sm bg-ink px-3 py-1.5 text-xs text-paper hover:bg-jade-deep"
          >
            搜索
          </button>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 pr-3 font-medium">账号</th>
                <th className="py-2 pr-3 font-medium">角色</th>
                <th className="py-2 pr-3 font-medium">会员</th>
                <th className="py-2 pr-3 font-medium">到期</th>
                <th className="py-2 pr-3 font-medium">验证</th>
                <th className="py-2 pr-3 font-medium">状态</th>
                <th className="py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((user) => (
                <tr key={user.id} className="border-b border-line/60">
                  <td className="py-2 pr-3">
                    <p className="break-all text-xs text-ink">
                      {user.email ?? user.phone ?? "—"}
                    </p>
                    <p className="text-[11px] text-muted">
                      #{user.id} · 注册 {fmtDate(user.created_at)}
                    </p>
                  </td>
                  <td className="py-2 pr-3 text-xs">
                    {user.role === "admin" ? "管理员" : "用户"}
                  </td>
                  <td className="py-2 pr-3 text-xs">
                    {user.plan === "member" ? "会员" : "免费"}
                  </td>
                  <td className="tnum py-2 pr-3 text-xs text-muted">
                    {user.plan === "member" ? fmtDate(user.plan_expires_at) : "—"}
                  </td>
                  <td className="py-2 pr-3 text-xs">
                    {user.email ? (user.email_verified ? "已验证" : "未验证") : "—"}
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      className={`inline-flex rounded-sm px-1.5 py-0.5 text-[11px] ${
                        user.status === "banned"
                          ? "bg-[#f8ece9] text-[#9a3f2c]"
                          : "bg-jade-soft text-jade-deep"
                      }`}
                    >
                      {user.status === "banned" ? "已封禁" : "正常"}
                    </span>
                  </td>
                  <td className="py-2 text-right">
                    <div className="flex justify-end gap-2 text-xs">
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(user);
                          setDays(365);
                        }}
                        className="text-jade-deep hover:underline"
                      >
                        会员
                      </button>
                      <button
                        type="button"
                        onClick={() => onToggleBan(user)}
                        className="text-loss hover:underline"
                      >
                        {user.status === "banned" ? "解封" : "封禁"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex items-center justify-between text-xs text-muted">
          <span>
            共 {total} 个用户 · 第 {page}/{pages} 页
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

      {editing ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-sm rounded-sm bg-surface p-6 shadow-lg">
            <h2 className="font-serif text-xl text-ink">调整会员</h2>
            <p className="mt-1 break-all text-xs text-muted">
              {editing.email ?? editing.phone}
            </p>
            <label className="mt-4 block text-xs text-muted">
              开通天数
              <input
                type="number"
                min={1}
                max={3650}
                value={days}
                onChange={(event) => setDays(Number(event.target.value))}
                className="mt-1 w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm text-ink"
              />
            </label>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditing(null)}
                className="rounded-sm border border-line px-3 py-1.5 text-xs text-ink-soft"
              >
                取消
              </button>
              <button
                type="button"
                onClick={onRevoke}
                disabled={busy}
                className="rounded-sm border border-loss/40 px-3 py-1.5 text-xs text-loss disabled:opacity-50"
              >
                取消会员
              </button>
              <button
                type="button"
                onClick={onGrant}
                disabled={busy}
                className="rounded-sm bg-ink px-3 py-1.5 text-xs text-paper disabled:opacity-50"
              >
                {busy ? "处理中…" : "开通/续费"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
