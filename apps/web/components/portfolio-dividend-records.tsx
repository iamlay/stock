"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getToken } from "@/lib/auth";
import {
  portfolioRequest,
  type PortfolioAccount,
  type PortfolioList,
} from "@/lib/portfolio";

type Receipt = {
  id: string;
  code: string;
  received_date: string;
  quantity: string | null;
  cash_per_share: string | null;
  gross_amount: string | null;
  tax_amount: string | null;
  net_amount: string;
  status: string;
  note: string;
};

export function PortfolioDividendRecords({ code }: { code: string }) {
  const [account, setAccount] = useState<PortfolioAccount | null>(null);
  const [name, setName] = useState("");
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    if (!getToken()) {
      window.location.href = `/login?next=/portfolio/${code}/dividends`;
      return;
    }
    try {
      const accounts = await portfolioRequest<PortfolioList>("/accounts");
      const first = accounts.items[0] ?? null;
      setAccount(first);
      if (first) {
        const [income, holdings] = await Promise.all([
          portfolioRequest<{ receipts: Receipt[] }>(`/accounts/${first.id}/income`),
          portfolioRequest<{
            positions: { code: string; name: string }[];
          }>(`/accounts/${first.id}/holdings`),
        ]);
        setReceipts(income.receipts.filter((row) => row.code === code));
        setName(holdings.positions.find((row) => row.code === code)?.name ?? code);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    void load();
  }, [load]);

  async function reverse(receiptId: string) {
    if (!account) return;
    if (!window.confirm("确认撤销这笔分红记录？原记录会保留审计链。")) return;
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "撤销失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  if (!account) {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm">还没有私人账本</p>
        <Link href="/portfolio" className="mt-3 inline-block text-sm text-jade-deep">
          去建立持仓 →
        </Link>
      </div>
    );
  }

  const active = receipts.filter((row) => row.status === "active");
  const total = active.reduce((sum, row) => sum + Number(row.net_amount), 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted">分红记录</p>
          <h1 className="mt-1 font-serif text-2xl">
            {code} {name}
          </h1>
          <p className="mt-1 text-sm text-muted">A股 · 人民币资产</p>
        </div>
        <Link
          href={`/portfolio/${code}/dividends/add`}
          className="rounded-xl bg-ink px-4 py-2.5 text-sm font-medium text-paper"
        >
          + 添加分红
        </Link>
      </div>
      {error ? <p className="text-sm text-loss">{error}</p> : null}
      <section className="card flex flex-wrap items-center justify-between gap-3 p-5">
        <p className="text-sm text-muted">累计已获分红</p>
        <p className="tnum text-2xl font-semibold text-amber">¥{total.toFixed(2)}</p>
      </section>
      <p className="rounded-xl border border-jade/20 bg-jade-soft/50 p-4 text-xs leading-6 text-jade-deep">
        派息日到账后可手动登记；登记的是实际到账金额。A股分红默认全额到账，实际被扣税时再填写税额。
      </p>
      {active.length ? (
        <div className="space-y-3">
          {active.map((row) => (
            <div
              key={row.id}
              className="card flex flex-wrap items-center justify-between gap-3 p-4"
            >
              <div>
                <p className="text-sm font-medium">{row.received_date}</p>
                <p className="tnum mt-1 text-xs text-muted">
                  {row.quantity && row.cash_per_share
                    ? `${row.quantity} 股 × ${row.cash_per_share} 元`
                    : "历史到账记录"}
                </p>
              </div>
              <div className="text-right">
                <p className="tnum text-lg font-medium text-amber">¥{row.net_amount}</p>
                <p className="text-xs text-muted">
                  {row.tax_amount && Number(row.tax_amount) > 0
                    ? `税额 ¥${row.tax_amount}`
                    : "未扣税"}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Link
                  href={`/portfolio/${code}/dividends/${row.id}/edit`}
                  className="text-xs text-jade-deep hover:underline"
                >
                  编辑
                </Link>
                <button
                  type="button"
                  onClick={() => reverse(row.id)}
                  disabled={busy}
                  className="text-xs text-loss hover:underline disabled:opacity-50"
                >
                  撤销
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card p-10 text-center">
          <p className="text-2xl">💰</p>
          <p className="mt-3 text-sm text-muted">暂无分红记录</p>
          <Link
            href={`/portfolio/${code}/dividends/add`}
            className="mt-4 inline-block rounded-xl bg-ink px-4 py-2.5 text-sm text-paper"
          >
            + 添加一笔
          </Link>
        </div>
      )}
      <Link href={`/portfolio/${code}`} className="inline-block text-sm text-jade-deep">
        ← 返回持仓详情
      </Link>
    </div>
  );
}
