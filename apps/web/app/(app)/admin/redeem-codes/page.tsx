"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  adminExportCsv,
  adminGenerateCodes,
  adminListCodes,
  adminRevokeCode,
  fetchMe,
  getToken,
  type AdminCode,
  type AdminCodeStats,
  type Me,
} from "@/lib/auth";

const STATUS_LABELS: Record<string, string> = {
  issued: "未使用",
  redeemed: "已兑换",
  expired: "已过期",
  revoked: "已作废",
};

const STATUS_STYLES: Record<string, string> = {
  issued: "bg-jade-soft text-jade-deep",
  redeemed: "bg-[#eef1f8] text-[#3d4f7c]",
  expired: "bg-[#f1efe8] text-ink-soft",
  revoked: "bg-[#f8ece9] text-[#9a3f2c]",
};

export default function AdminRedeemCodesPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [items, setItems] = useState<AdminCode[]>([]);
  const [stats, setStats] = useState<AdminCodeStats | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [count, setCount] = useState(10);
  const [days, setDays] = useState(365);
  const [validDays, setValidDays] = useState(90);
  const [channel, setChannel] = useState("manual");
  const [plan, setPlan] = useState("member");
  const [generated, setGenerated] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (status: string) => {
    const data = await adminListCodes(status || undefined);
    setItems(data.items);
    setStats(data.stats);
  }, []);

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
        await load("");
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [load, router]);

  async function onGenerate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await adminGenerateCodes({ count, days, valid_days: validDays, channel, plan });
      setGenerated(result.codes.map((item) => item.code));
      setMessage(`已生成 ${result.codes.length} 个兑换码，批次 ${result.batch_id.slice(0, 8)}`);
      await load(statusFilter);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(code: string) {
    setError(null);
    try {
      await adminRevokeCode(code);
      setMessage(`已作废 ${code}`);
      await load(statusFilter);
    } catch (err) {
      setError(err instanceof Error ? err.message : "作废失败");
    }
  }

  async function onExport() {
    setError(null);
    try {
      const blob = await adminExportCsv(statusFilter || undefined);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "redeem-codes.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败");
    }
  }

  async function onCopy() {
    await navigator.clipboard.writeText(generated.join("\n"));
    setMessage(`已复制 ${generated.length} 个兑换码`);
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }

  if (forbidden) {
    return (
      <div className="py-20 text-center">
        <p className="text-sm text-muted">当前账号没有管理员权限。</p>
        <Link href="/account" className="mt-3 inline-block text-sm text-jade-deep hover:underline">
          返回个人中心
        </Link>
      </div>
    );
  }

  if (!me) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">兑换码管理</h1>
          <p className="mt-1 text-sm text-muted">批量生成、导出、作废；仅管理员可见</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onExport}
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft hover:border-ink"
          >
            导出 CSV
          </button>
          <Link
            href="/account"
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft hover:border-ink"
          >
            个人中心
          </Link>
        </div>
      </div>

      {stats ? (
        <section className="grid gap-3 sm:grid-cols-5">
          {[
            ["总数", stats.total],
            ["未使用", stats.issued],
            ["已兑换", stats.redeemed],
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
          <label className="flex w-24 flex-col gap-1">
            <span className="text-xs text-muted">码有效期</span>
            <input
              type="number"
              min={1}
              max={3650}
              value={validDays}
              onChange={(event) => setValidDays(Number(event.target.value))}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-32 flex-col gap-1">
            <span className="text-xs text-muted">渠道</span>
            <input
              value={channel}
              onChange={(event) => setChannel(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            />
          </label>
          <label className="flex w-24 flex-col gap-1">
            <span className="text-xs text-muted">套餐</span>
            <select
              value={plan}
              onChange={(event) => setPlan(event.target.value)}
              className="rounded-sm border border-line bg-surface px-2 py-2 text-sm"
            >
              <option value="member">会员</option>
              <option value="trial">试用</option>
            </select>
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
              <p className="text-xs text-muted">本批次兑换码</p>
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
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-medium text-ink">兑换码列表</h2>
          <select
            value={statusFilter}
            onChange={(event) => {
              const value = event.target.value;
              setStatusFilter(value);
              load(value).catch((err) =>
                setError(err instanceof Error ? err.message : "加载失败"),
              );
            }}
            className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value="">全部状态</option>
            <option value="issued">未使用</option>
            <option value="redeemed">已兑换</option>
            <option value="expired">已过期</option>
            <option value="revoked">已作废</option>
          </select>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 font-medium">兑换码</th>
                <th className="py-2 font-medium">套餐</th>
                <th className="py-2 font-medium">天数</th>
                <th className="py-2 font-medium">渠道</th>
                <th className="py-2 font-medium">状态</th>
                <th className="py-2 font-medium">有效期</th>
                <th className="py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.code} className="border-b border-line/60">
                  <td className="tnum py-2 font-mono text-xs">{item.code}</td>
                  <td className="py-2">{item.plan === "member" ? "会员" : "试用"}</td>
                  <td className="tnum py-2">{item.duration_days}</td>
                  <td className="py-2 text-ink-soft">{item.channel}</td>
                  <td className="py-2">
                    <span
                      className={`inline-flex rounded-sm px-1.5 py-0.5 text-[11px] ${
                        STATUS_STYLES[item.status] ?? "bg-black/5 text-ink-soft"
                      }`}
                    >
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </td>
                  <td className="tnum py-2 text-xs text-muted">
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
        {items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted">还没有兑换码，先生成一批。</p>
        ) : null}
      </section>
    </div>
  );
}
