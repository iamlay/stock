"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  adminGenerateInvites,
  adminListInviteBatches,
  adminListInvites,
  adminRevokeInvite,
  fetchMe,
  getToken,
  type AdminInvite,
  type AdminInviteBatch,
  type AdminInviteStats,
} from "@/lib/auth";

const PAGE_SIZE = 10;

const STATUS_LABELS: Record<string, string> = {
  issued: "未使用",
  redeemed: "已用完",
  expired: "已过期",
  revoked: "已作废",
};

export default function AdminInvitesPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [items, setItems] = useState<AdminInvite[]>([]);
  const [stats, setStats] = useState<AdminInviteStats | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [batchFilter, setBatchFilter] = useState("");
  const [search, setSearch] = useState("");
  const [batches, setBatches] = useState<AdminInviteBatch[]>([]);
  const [count, setCount] = useState(10);
  const [maxUses, setMaxUses] = useState(1);
  const [validDays, setValidDays] = useState(90);
  const [note, setNote] = useState("内测");
  const [generated, setGenerated] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load(
    targetPage = 1,
    nextStatus = statusFilter,
    nextBatch = batchFilter,
    nextSearch = search,
  ) {
    const data = await adminListInvites({
      status: nextStatus || undefined,
      batch_id: nextBatch || undefined,
      q: nextSearch || undefined,
      page: targetPage,
      page_size: PAGE_SIZE,
    });
    setItems(data.items);
    setStats(data.stats);
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
        await Promise.all([load(1), adminListInviteBatches().then(setBatches)]);
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function onGenerate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await adminGenerateInvites({
        count,
        max_uses: maxUses,
        valid_days: validDays,
        note: note || undefined,
      });
      setGenerated(result.codes.map((item) => item.code));
      setMessage(`已生成 ${result.codes.length} 个邀请码，批次 ${result.batch_id.slice(0, 8)}`);
      await Promise.all([load(1), adminListInviteBatches().then(setBatches)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(code: string) {
    setError(null);
    try {
      await adminRevokeInvite(code);
      setMessage(`已作废 ${code}`);
      await load(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "作废失败");
    }
  }

  async function onCopy() {
    await navigator.clipboard.writeText(generated.join("\n"));
    setMessage(`已复制 ${generated.length} 个邀请码`);
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
          <h1 className="font-serif text-3xl text-ink">邀请码管理</h1>
          <p className="mt-1 text-sm text-muted">注册邀请码的批次、次数与作废</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/admin/users"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            用户管理
          </Link>
          <Link
            href="/admin/redeem-codes"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            兑换码管理
          </Link>
        </div>
      </div>

      {stats ? (
        <section className="grid gap-3 sm:grid-cols-5">
          {[
            ["总数", stats.total],
            ["未使用", stats.issued],
            ["已用完", stats.redeemed],
            ["已过期", stats.expired],
            ["已作废", stats.revoked],
          ].map(([label, value]) => (
            <div key={String(label)} className="card p-4">
              <p className="text-xs text-muted">{label}</p>
              <p className="tnum mt-2 text-xl font-semibold text-ink">{value}</p>
            </div>
          ))}
        </section>
      ) : null}

      <section className="card p-5">
        <h2 className="text-base font-medium text-ink">批量生成</h2>
        <form onSubmit={onGenerate} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="flex w-20 flex-col gap-1">
            <span className="text-xs text-muted">数量</span>
            <input
              type="number"
              min={1}
              max={500}
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-24 flex-col gap-1">
            <span className="text-xs text-muted">每码次数</span>
            <input
              type="number"
              min={1}
              max={1000}
              value={maxUses}
              onChange={(event) => setMaxUses(Number(event.target.value))}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-24 flex-col gap-1">
            <span className="text-xs text-muted">有效期</span>
            <input
              type="number"
              min={1}
              max={3650}
              value={validDays}
              onChange={(event) => setValidDays(Number(event.target.value))}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-40 flex-col gap-1">
            <span className="text-xs text-muted">备注</span>
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep disabled:opacity-50"
          >
            {busy ? "生成中…" : "生成"}
          </button>
        </form>

        {message ? <p className="mt-3 text-xs text-jade-deep">{message}</p> : null}
        {error ? <p className="mt-3 text-xs text-loss">{error}</p> : null}

        {generated.length > 0 ? (
          <div className="mt-4 rounded-sm border border-line bg-paper/60 p-3">
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted">本批次邀请码</p>
              <button type="button" onClick={onCopy} className="text-xs text-jade-deep hover:underline">
                复制全部
              </button>
            </div>
            <p className="tnum mt-2 break-all font-mono text-xs leading-6 text-ink">
              {generated.join("  ")}
            </p>
          </div>
        ) : null}
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="mr-auto text-base font-medium text-ink">邀请码列表</h2>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") load(1, statusFilter, batchFilter, search);
            }}
            placeholder="搜索邀请码"
            className="w-40 rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          />
          <select
            value={batchFilter}
            onChange={(event) => {
              setBatchFilter(event.target.value);
              load(1, statusFilter, event.target.value, search);
            }}
            className="max-w-48 rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">全部批次</option>
            {batches.map((batch) => (
              <option key={batch.batch_id} value={batch.batch_id}>
                {batch.batch_id.slice(0, 8)} · {batch.total} 个
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              load(1, event.target.value, batchFilter, search);
            }}
            className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">全部状态</option>
            <option value="issued">未使用</option>
            <option value="redeemed">已用完</option>
            <option value="revoked">已作废</option>
            <option value="expired">已过期</option>
          </select>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 pr-3 font-medium">邀请码</th>
                <th className="py-2 pr-3 font-medium">次数</th>
                <th className="py-2 pr-3 font-medium">备注</th>
                <th className="py-2 pr-3 font-medium">状态</th>
                <th className="py-2 pr-3 font-medium">有效期</th>
                <th className="py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.code} className="border-b border-line/60">
                  <td className="tnum py-2 pr-3 font-mono text-xs">{item.code}</td>
                  <td className="tnum py-2 pr-3 text-xs">
                    {item.used_count}/{item.max_uses}
                  </td>
                  <td className="py-2 pr-3 text-xs text-muted">{item.note ?? "—"}</td>
                  <td className="py-2 pr-3">
                    <span className="rounded-sm bg-[#eef1f8] px-1.5 py-0.5 text-[11px] text-[#3d4f7c]">
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </td>
                  <td className="tnum py-2 pr-3 text-xs text-muted">
                    {item.expires_at ? item.expires_at.slice(0, 10) : "—"}
                  </td>
                  <td className="py-2 text-right">
                    {item.status === "issued" ? (
                      <button
                        type="button"
                        onClick={() => onRevoke(item.code)}
                        className="text-xs text-loss hover:underline"
                      >
                        作废
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
