"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { getToken } from "@/lib/auth";
import { portfolioRequest, type PortfolioList } from "@/lib/portfolio";
import { inputTotal, shanghaiToday } from "@/lib/portfolio-positions";

const input =
  "w-full rounded-xl border border-line bg-surface px-4 py-3 text-base outline-none focus:border-jade";

export function PortfolioDividendAdd({
  code,
  receiptId,
}: {
  code: string;
  receiptId?: string;
}) {
  const router = useRouter();
  const [accountId, setAccountId] = useState("");
  const [version, setVersion] = useState(0);
  const [name, setName] = useState(code);
  const [quantity, setQuantity] = useState("");
  const [cash, setCash] = useState("");
  const [tax, setTax] = useState("");
  const [date, setDate] = useState(shanghaiToday());
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const taxHelp = useRef<HTMLDialogElement>(null);

  const load = useCallback(async () => {
    if (!getToken()) {
      window.location.href = `/login?next=/portfolio/${code}/dividends/add`;
      return;
    }
    try {
      const accounts = await portfolioRequest<PortfolioList>("/accounts");
      const first = accounts.items[0];
      if (!first) {
        router.replace("/portfolio");
        return;
      }
      setAccountId(first.id);
      setVersion(first.version);
      const holdings = await portfolioRequest<{
        positions: { code: string; name: string; quantity: string }[];
      }>(`/accounts/${first.id}/holdings`);
      const position = holdings.positions.find((row) => row.code === code);
      if (position) {
        setName(position.name);
        setQuantity(position.quantity.replace(/\.0+$/, ""));
      }
      if (receiptId) {
        const income = await portfolioRequest<{
          receipts: {
            id: string;
            code: string;
            received_date: string;
            quantity: string | null;
            cash_per_share: string | null;
            gross_amount: string | null;
            tax_amount: string | null;
            net_amount: string;
            note: string;
            status: string;
          }[];
        }>(`/accounts/${first.id}/income`);
        const receipt = income.receipts.find(
          (row) => row.id === receiptId && row.code === code && row.status === "active",
        );
        if (!receipt) {
          setError("分红记录不存在或已撤销");
        } else {
          setDate(receipt.received_date);
          setQuantity(receipt.quantity?.replace(/\.0+$/, "") ?? "");
          setCash(receipt.cash_per_share ?? "");
          setTax(receipt.tax_amount ?? "");
          setNote(receipt.note ?? "");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [code, receiptId, router]);

  useEffect(() => {
    void load();
  }, [load]);

  const gross = inputTotal(quantity || "0", cash || "0", "0");
  const taxValue = Number(tax || "0");
  const grossValue = gross == null ? null : Number(gross);
  const net =
    grossValue == null || !Number.isFinite(taxValue)
      ? null
      : Math.max(0, grossValue - taxValue);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!accountId || busy) return;
    if (gross == null || net == null) {
      setError("数量和每股派息格式不正确");
      return;
    }
    if (taxValue < 0 || taxValue > grossValue!) {
      setError("税额不能为负或超过税前金额");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await portfolioRequest(
        receiptId
          ? `/accounts/${accountId}/receipts/${receiptId}`
          : `/accounts/${accountId}/receipts`,
        {
          method: receiptId ? "PATCH" : "POST",
          body: JSON.stringify(
            receiptId
              ? {
                  expected_version: version,
                  received_date: date,
                  gross_amount: gross,
                  tax_amount: tax || "0",
                  net_amount: net.toFixed(2),
                  quantity,
                  cash_per_share: cash,
                  note,
                }
              : {
                  expected_version: version,
                  request_id: crypto.randomUUID(),
                  entitlement_id: null,
                  code,
                  quantity,
                  cash_per_share: cash,
                  received_date: date,
                  gross_amount: gross,
                  tax_amount: tax || "0",
                  net_amount: net.toFixed(2),
                  note,
                },
          ),
        },
      );
      router.push(`/portfolio/${code}/dividends`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="py-20 text-center text-sm text-muted">加载中…</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <p className="text-xs text-muted">
          {receiptId ? "编辑分红记录" : "添加分红记录"}
        </p>
        <h1 className="mt-1 font-serif text-2xl">
          {code} {name}
        </h1>
        <p className="mt-1 text-sm text-muted">A股 · 人民币</p>
      </div>
      {error ? <p className="text-sm text-loss">{error}</p> : null}
      <form onSubmit={submit} className="space-y-5">
        <section className="card space-y-5 p-5">
          <label className="block space-y-2 text-sm">
            <span>入账日期 *</span>
            <input
              type="date"
              value={date}
              max={shanghaiToday()}
              onChange={(event) => setDate(event.target.value)}
              required
              className={input}
            />
          </label>
          <label className="block space-y-2 text-sm">
            <span>持仓数量 *</span>
            <input
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              inputMode="decimal"
              placeholder="分红入账时的持仓股数"
              required
              className={input}
            />
          </label>
          <label className="block space-y-2 text-sm">
            <span>每股派息 *</span>
            <div className="flex items-center gap-3">
              <input
                value={cash}
                onChange={(event) => setCash(event.target.value)}
                inputMode="decimal"
                placeholder="每股派息金额（人民币）"
                required
                className={input}
              />
              <span className="shrink-0 text-xs text-muted">人民币/股</span>
            </div>
          </label>
          <div className="rounded-xl border border-amber/30 bg-amber-soft/30 p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-amber">红利税（选填）</span>
              <button
                type="button"
                onClick={() => taxHelp.current?.showModal()}
                className="flex h-6 w-6 items-center justify-center rounded-full border border-amber/40 text-xs text-amber"
                aria-label="红利税说明"
              >
                ?
              </button>
            </div>
            <input
              value={tax}
              onChange={(event) => setTax(event.target.value)}
              inputMode="decimal"
              placeholder="扣税金额"
              className={`${input} mt-3`}
            />
            <p className="mt-2 text-xs leading-6 text-muted">
              A股分红默认全额到账，如实际被扣税可手动填写。
            </p>
          </div>
          <label className="block space-y-2 text-sm">
            <span>实际到账金额 *</span>
            <input
              value={net == null ? "" : net.toFixed(2)}
              readOnly
              className={`${input} bg-paper`}
            />
            <span className="text-xs text-muted">= 数量 × 每股派息 - 红利税</span>
          </label>
          <label className="block space-y-2 text-sm">
            <span>备注（可选）</span>
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={500}
              placeholder="券商到账说明"
              className={input}
            />
          </label>
        </section>
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:opacity-50"
        >
          {busy ? "保存中…" : receiptId ? "保存修改" : "确认添加"}
        </button>
      </form>
      <Link
        href={`/portfolio/${code}/dividends`}
        className="inline-block text-sm text-jade-deep"
      >
        ← 返回分红记录
      </Link>

      <dialog
        ref={taxHelp}
        className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl border border-line bg-surface p-6 text-ink backdrop:bg-black/40"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-medium">A股红利税怎么算</h2>
          <button
            type="button"
            onClick={() => taxHelp.current?.close()}
            className="text-xl leading-none text-muted"
            aria-label="关闭"
          >
            ×
          </button>
        </div>
        <div className="mt-4 space-y-3 text-sm leading-7 text-ink-soft">
          <p>税率取决于卖出时的持股时间，除息时不扣，卖出时才补。</p>
          <ul className="space-y-1">
            <li>持股 ≤ 1 个月：20%</li>
            <li>持股 1 个月–1 年：10%</li>
            <li>持股 &gt; 1 年：0%</li>
          </ul>
          <p>
            A股分红到账时通常全额到账。系统默认按全额登记，不替你猜税；
            只有券商实际扣税时，才填写扣税金额。
          </p>
          <p className="rounded-xl bg-paper p-3 text-xs leading-6 text-muted">
            例：1000 股 × 0.5 元 = 500 元。免税填 0；10% 填 50；20% 填 100。
          </p>
        </div>
      </dialog>
    </div>
  );
}
