"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getToken } from "@/lib/auth";
import {
  portfolioRequest,
  type PortfolioAccount,
  type PortfolioList,
} from "@/lib/portfolio";

type Entitlement = {
  id: string;
  code: string;
  record_date: string;
  payment_date: string | null;
  eligible_quantity: string;
  cash_per_share: string;
  gross_amount: string;
  received_amount: string;
  remaining_amount: string;
  status: string;
  review_reasons: string[];
};

type Receipt = {
  id: string;
  entitlement_id: string | null;
  code: string;
  received_date: string;
  gross_amount: string | null;
  tax_amount: string | null;
  net_amount: string;
  status: string;
  note: string;
  reversed_at: string | null;
};

type Income = {
  summary: {
    gross_amount: string;
    received_amount: string;
    remaining_amount: string;
    unlinked_received_amount: string;
    entitlement_count: number;
    pending_count: number;
  };
  entitlements: Entitlement[];
  receipts: Receipt[];
};

const STATUS: Record<string, string> = {
  pending: "待收",
  partial: "部分到账",
  settled: "已收齐",
  review: "待核对",
  void: "已失效",
  active: "有效",
  reversed: "已撤销",
};

const input =
  "w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-jade";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function PortfolioIncome() {
  const [account, setAccount] = useState<PortfolioAccount | null>(null);
  const [income, setIncome] = useState<Income | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [entitlementId, setEntitlementId] = useState("");
  const [code, setCode] = useState("");
  const [receivedDate, setReceivedDate] = useState(today());
  const [net, setNet] = useState("");
  const [gross, setGross] = useState("");
  const [tax, setTax] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    if (!getToken()) {
      window.location.href = "/login?next=/portfolio/income";
      return;
    }
    try {
      const accounts = await portfolioRequest<PortfolioList>("/accounts");
      const first = accounts.items[0] ?? null;
      setAccount(first);
      if (first) {
        const data = await portfolioRequest<Income>(
          `/accounts/${first.id}/income`,
        );
        setIncome(data);
      } else {
        setIncome(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function refresh() {
    if (!account) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await portfolioRequest<{
        created: number;
        updated: number;
        voided: number;
      }>(`/accounts/${account.id}/income/refresh`, { method: "POST" });
      await load();
      setMessage(
        `重算完成：新增 ${result.created}，更新 ${result.updated}，失效 ${result.voided}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "重算失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitReceipt(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!account) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const selected = income?.entitlements.find((row) => row.id === entitlementId);
      await portfolioRequest(`/accounts/${account.id}/receipts`, {
        method: "POST",
        body: JSON.stringify({
          expected_version: account.version,
          request_id: crypto.randomUUID(),
          entitlement_id: entitlementId || null,
          code: selected?.code || code,
          received_date: receivedDate,
          net_amount: net,
          gross_amount: gross || null,
          tax_amount: tax || null,
          note,
        }),
      });
      setNet("");
      setGross("");
      setTax("");
      setNote("");
      await load();
      setMessage("到账记录已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function reverse(receiptId: string) {
    if (!account) return;
    if (!window.confirm("确认撤销这笔到账记录？记录会保留审计链。")) return;
    setBusy(true);
    setError("");
    try {
      await portfolioRequest(
        `/accounts/${account.id}/receipts/${receiptId}/reverse`,
        {
          method: "POST",
          body: JSON.stringify({ expected_version: account.version }),
        },
      );
      await load();
      setMessage("到账记录已撤销");
    } catch (err) {
      setError(err instanceof Error ? err.message : "撤销失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }

  if (!account) {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm text-ink">还没有私人账本</p>
        <Link
          href="/portfolio"
          className="mt-4 inline-block text-sm text-jade-deep hover:underline"
        >
          先建立持仓账本 →
        </Link>
      </div>
    );
  }

  const selected = income?.entitlements.find((row) => row.id === entitlementId);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">收息账本</h1>
          <p className="mt-1 text-sm text-muted">
            {account.name} · 应收与实收分开核对
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={refresh}
            disabled={busy}
            className="rounded-sm border border-line bg-surface px-3 py-2 text-sm text-jade-deep disabled:opacity-50"
          >
            重算应收
          </button>
          <Link
            href="/portfolio"
            className="rounded-sm border border-line bg-surface px-3 py-2 text-sm text-ink-soft hover:border-ink"
          >
            返回持仓
          </Link>
        </div>
      </div>

      {error ? <p className="text-sm text-loss">{error}</p> : null}
      {message ? <p className="text-sm text-jade-deep">{message}</p> : null}

      <section className="grid gap-3 sm:grid-cols-3">
        {[
          ["税前应收", income?.summary.gross_amount ?? "0.00"],
          ["已到账净额", income?.summary.received_amount ?? "0.00"],
          ["待收余额", income?.summary.remaining_amount ?? "0.00"],
        ].map(([label, value]) => (
          <div key={label} className="card p-5">
            <p className="text-xs text-muted">{label}</p>
            <p className="tnum mt-2 text-2xl font-semibold text-ink">¥{value}</p>
          </div>
        ))}
      </section>

      <p className="text-xs leading-6 text-muted">
        应收只根据已核对、正式实施、登记日和每股现金完整的现金分红计算。
        未关联到账 {income?.summary.unlinked_received_amount ?? "0.00"} 元，尚未计入应收核对。
      </p>

      <section className="card overflow-hidden">
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-medium text-ink">应收分红</h2>
          <p className="mt-1 text-xs text-muted">
            共 {income?.summary.entitlement_count ?? 0} 笔，待收{" "}
            {income?.summary.pending_count ?? 0} 笔
          </p>
        </div>
        {income?.entitlements.length ? (
          <div className="divide-y divide-line">
            {income.entitlements.map((row) => (
              <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-sm font-medium text-ink">
                    {row.code} · 登记 {row.record_date}
                  </p>
                  <p className="tnum mt-1 text-xs text-muted">
                    {row.eligible_quantity} 股 × {row.cash_per_share} 元 = ¥
                    {row.gross_amount}
                  </p>
                </div>
                <div className="text-right text-xs">
                  <p className={row.status === "settled" ? "text-jade-deep" : "text-amber"}>
                    {STATUS[row.status] ?? row.status}
                  </p>
                  <p className="tnum mt-1 text-muted">
                    已收 ¥{row.received_amount} · 待收 ¥{row.remaining_amount}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="p-6 text-sm text-muted">
            暂无可计算应收。请先确认持仓，点击“重算应收”。
          </p>
        )}
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-medium text-ink">登记到账</h2>
        <p className="mt-1 text-xs text-muted">
          到账金额按实际入账日期记录；只知道净额时可以不填税前和税额。
        </p>
        <form onSubmit={submitReceipt} className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-muted">
            关联应收
            <select
              value={entitlementId}
              onChange={(event) => {
                setEntitlementId(event.target.value);
                const row = income?.entitlements.find(
                  (item) => item.id === event.target.value,
                );
                setCode(row?.code ?? "");
              }}
              className={`${input} mt-1`}
            >
              <option value="">不关联（单独记一笔到账）</option>
              {income?.entitlements.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.code} · 登记 {row.record_date} · ¥{row.gross_amount}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-muted">
            股票代码
            <input
              value={selected?.code ?? code}
              onChange={(event) => setCode(event.target.value)}
              disabled={Boolean(selected)}
              placeholder="603165"
              className={`${input} mt-1`}
            />
          </label>
          <label className="text-xs text-muted">
            到账日期
            <input
              type="date"
              value={receivedDate}
              onChange={(event) => setReceivedDate(event.target.value)}
              className={`${input} mt-1`}
            />
          </label>
          <label className="text-xs text-muted">
            净额
            <input
              value={net}
              onChange={(event) => setNet(event.target.value)}
              placeholder="500.00"
              className={`${input} mt-1`}
            />
          </label>
          <label className="text-xs text-muted">
            税前金额（可选）
            <input
              value={gross}
              onChange={(event) => setGross(event.target.value)}
              placeholder="500.00"
              className={`${input} mt-1`}
            />
          </label>
          <label className="text-xs text-muted">
            税额（可选）
            <input
              value={tax}
              onChange={(event) => setTax(event.target.value)}
              placeholder="0.00"
              className={`${input} mt-1`}
            />
          </label>
          <label className="text-xs text-muted sm:col-span-2">
            备注
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="券商到账说明"
              className={`${input} mt-1`}
            />
          </label>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper disabled:opacity-50"
            >
              {busy ? "保存中…" : "保存到账"}
            </button>
          </div>
        </form>
      </section>

      <section className="card overflow-hidden">
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-medium text-ink">到账记录</h2>
        </div>
        {income?.receipts.length ? (
          <div className="divide-y divide-line">
            {income.receipts.map((row) => (
              <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-sm text-ink">
                    {row.code} · {row.received_date}
                  </p>
                  <p className="tnum mt-1 text-xs text-muted">
                    净额 ¥{row.net_amount}
                    {row.gross_amount ? ` · 税前 ¥${row.gross_amount}` : ""}
                    {row.tax_amount ? ` · 税额 ¥${row.tax_amount}` : ""}
                  </p>
                </div>
                <div className="text-right text-xs">
                  <span className={row.status === "active" ? "text-jade-deep" : "text-muted"}>
                    {STATUS[row.status] ?? row.status}
                  </span>
                  {row.status === "active" ? (
                    <button
                      type="button"
                      onClick={() => reverse(row.id)}
                      className="ml-3 text-loss hover:underline"
                    >
                      撤销
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="p-6 text-sm text-muted">还没有到账记录。</p>
        )}
      </section>
    </div>
  );
}
