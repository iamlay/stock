"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EquityCurve } from "@/components/equity-curve";
import type { BacktestResult } from "@/lib/api";
import {
  clearToken,
  fetchHistory,
  fetchHistoryDetail,
  fetchMe,
  getToken,
  redeem,
  type HistoryItem,
  type Me,
} from "@/lib/auth";
import { getStrategy } from "@/lib/mock";

function fmtDate(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

export default function AccountPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [detail, setDetail] = useState<BacktestResult | null>(null);
  const [code, setCode] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [redeeming, setRedeeming] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    fetchMe()
      .then((profile) => {
        setMe(profile);
        if (profile.is_member) {
          return fetchHistory().then(setHistory);
        }
        return undefined;
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function onRedeem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setRedeeming(true);
    try {
      const result = await redeem(code.trim());
      const profile = await fetchMe();
      setMe(profile);
      setMessage(`兑换成功，会员有效期至 ${fmtDate(result.plan_expires_at)}`);
      setCode("");
      if (profile.is_member) {
        setHistory(await fetchHistory());
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "兑换失败");
    } finally {
      setRedeeming(false);
    }
  }

  async function onView(id: number) {
    setError(null);
    try {
      setDetail(await fetchHistoryDetail(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    }
  }

  function onLogout() {
    clearToken();
    router.push("/login");
    router.refresh();
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }

  if (!me) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">个人中心</h1>
          <p className="mt-1 text-sm text-muted">账号、会员与回测历史</p>
        </div>
        <div className="flex items-center gap-2">
          {me.role === "admin" ? (
            <Link
              href="/admin/redeem-codes"
              className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
            >
              兑换码管理
            </Link>
          ) : null}
          <button
            type="button"
            onClick={onLogout}
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft hover:border-ink"
          >
            退出登录
          </button>
        </div>
      </div>

      <section className="grid gap-4 sm:grid-cols-3">
        <div className="card p-5">
          <p className="text-xs text-muted">账号</p>
          <p className="mt-2 break-all text-lg font-medium text-ink">
            {me.email ?? me.phone ?? "—"}
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">会员状态</p>
          <p className={`mt-2 text-lg font-medium ${me.is_member ? "text-jade-deep" : "text-ink"}`}>
            {me.is_member ? "会员" : "免费用户"}
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted">有效期</p>
          <p className="tnum mt-2 text-lg font-medium text-ink">
            {me.is_member ? fmtDate(me.plan_expires_at) : "—"}
          </p>
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-base font-medium text-ink">兑换码</h2>
        <p className="mt-1 text-xs text-muted">
          输入第三方平台发放的兑换码，会员时长可叠加。
        </p>
        <form onSubmit={onRedeem} className="mt-4 flex flex-wrap gap-2">
          <input
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            placeholder="例如 SL8K2P4Q1M"
            className="w-56 rounded-sm border border-line bg-surface px-3 py-2 text-sm uppercase outline-none focus:border-jade"
          />
          <button
            type="submit"
            disabled={redeeming || code.trim().length < 4}
            className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-jade-deep disabled:opacity-50"
          >
            {redeeming ? "兑换中…" : "兑换"}
          </button>
        </form>
        {message ? <p className="mt-3 text-xs text-jade-deep">{message}</p> : null}
        {error ? <p className="mt-3 text-xs text-loss">{error}</p> : null}
      </section>

      <section className="card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium text-ink">回测历史</h2>
            <p className="mt-1 text-xs text-muted">
              {me.is_member ? "最近 50 次保存的结果" : "开通会员后可查看已保存的回测"}
            </p>
          </div>
          {!me.is_member ? (
            <Link href="/pricing" className="text-xs text-jade-deep hover:underline">
              了解会员 →
            </Link>
          ) : null}
        </div>

        {me.is_member ? (
          history.length > 0 ? (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="py-2 font-medium">时间</th>
                    <th className="py-2 font-medium">标的</th>
                    <th className="py-2 font-medium">策略</th>
                    <th className="py-2 text-right font-medium">累计收益</th>
                    <th className="py-2 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item) => (
                    <tr key={item.id} className="border-b border-line/60">
                      <td className="py-2 text-ink-soft">{item.created_at.slice(0, 16).replace("T", " ")}</td>
                      <td className="tnum py-2">{item.code}</td>
                      <td className="py-2">{getStrategy(item.strategy)?.name ?? item.strategy}</td>
                      <td className={`tnum py-2 text-right ${item.total_return >= 0 ? "text-loss" : "text-jade"}`}>
                        {item.total_return > 0 ? "+" : ""}
                        {item.total_return}%
                      </td>
                      <td className="py-2 text-right">
                        <button
                          type="button"
                          onClick={() => onView(item.id)}
                          className="text-xs text-jade-deep hover:underline"
                        >
                          查看
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted">还没有保存的回测，去策略页跑一次吧。</p>
          )
        ) : null}
      </section>

      {detail ? (
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-medium text-ink">
                历史快照 · {getStrategy(detail.strategy)?.name ?? detail.strategy}
              </h2>
              <p className="mt-1 text-xs text-muted">
                {detail.code} · {detail.start} → {detail.end}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setDetail(null)}
              className="text-xs text-muted hover:text-ink"
            >
              收起
            </button>
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["累计收益", `${detail.metrics.total_return}%`],
              ["最大回撤", `${detail.metrics.max_drawdown}%`],
              ["夏普", detail.metrics.sharpe.toFixed(2)],
              ["交易次数", String(detail.metrics.trades)],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="tnum mt-1 text-sm font-medium text-ink">{value}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-4">
            <EquityCurve
              id={`history-${detail.run_id ?? "run"}`}
              points={detail.equity.map((point) => point.equity)}
              height={200}
            />
          </div>
        </section>
      ) : null}
    </div>
  );
}
