"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { getToken } from "@/lib/auth";
import {
  portfolioRequest,
  type PortfolioAccount,
  type PortfolioList,
} from "@/lib/portfolio";

type CalendarItem = {
  date_type: string;
  date_type_label: string;
  code: string;
  stage: string;
  plan: string;
  amount: string | null;
  remaining_amount: string | null;
  reason: string | null;
};

type Day = { date: string; items: CalendarItem[] };

type Home = {
  year: number;
  as_of: string;
  summary: {
    received: string;
    pending: string;
    proposal: string;
    contract_pending: string;
    unknown_count: number;
    next_payment: { code: string; amount: string; payment_date: string } | null;
  };
  monthly: { month: string; received: string; pending: string; proposal: string }[];
  calendar: Day[];
  unknown: {
    code: string;
    plan: string;
    record_date: string | null;
    payment_date: string | null;
    reason: string | null;
  }[];
  entitlements: {
    id: string;
    code: string;
    record_date: string;
    payment_date: string | null;
    gross_amount: string;
    received_amount: string;
    remaining_amount: string;
    status: string;
  }[];
};

const STATUS: Record<string, string> = {
  pending: "待收",
  partial: "部分到账",
  settled: "已收齐",
  review: "待核对",
  void: "已失效",
};

function money(value: string | null | undefined): string {
  return value == null ? "—" : `¥${value}`;
}

function monthDays(year: number, month: number): (string | null)[] {
  const first = new Date(year, month - 1, 1).getDay();
  const count = new Date(year, month, 0).getDate();
  return [
    ...Array.from({ length: first }, () => null),
    ...Array.from({ length: count }, (_, index) => {
      const day = String(index + 1).padStart(2, "0");
      return `${year}-${String(month).padStart(2, "0")}-${day}`;
    }),
  ];
}

export function IncomeHome() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [account, setAccount] = useState<PortfolioAccount | null>(null);
  const [data, setData] = useState<Home | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async (targetYear: number) => {
    setLoading(true);
    setError("");
    if (!getToken()) {
      window.location.href = "/login?next=/income";
      return;
    }
    try {
      const accounts = await portfolioRequest<PortfolioList>("/accounts");
      const first = accounts.items[0] ?? null;
      setAccount(first);
      if (first) {
        const result = await portfolioRequest<Home>(
          `/accounts/${first.id}/income/home?year=${targetYear}`,
        );
        setData(result);
      } else {
        setData(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(year);
  }, [load, year]);

  const byDate = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    for (const day of data?.calendar ?? []) map.set(day.date, day.items);
    return map;
  }, [data]);

  const monthPrefix = `${year}-${String(month).padStart(2, "0")}`;
  const maxMonthly = Math.max(
    1,
    ...(data?.monthly ?? []).map((row) =>
      Math.max(Number(row.received), Number(row.pending), Number(row.proposal)),
    ),
  );

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }

  if (!account) {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm text-ink">还没有私人账本</p>
        <Link href="/portfolio" className="mt-4 inline-block text-sm text-jade-deep hover:underline">
          先建立持仓账本 →
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">Income</p>
          <h1 className="mt-1 font-serif text-3xl text-ink">收息首页</h1>
          <p className="mt-1 text-sm text-muted">{account.name} · 已收、待收与分红日历</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={year}
            onChange={(event) => {
              const next = Number(event.target.value);
              setYear(next);
              setSelected(null);
            }}
            className="rounded-sm border border-line bg-surface px-2.5 py-2 text-sm"
          >
            {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map(
              (value) => (
                <option key={value} value={value}>
                  {value} 年
                </option>
              ),
            )}
          </select>
          <Link
            href="/portfolio/income"
            className="rounded-sm border border-line bg-surface px-3 py-2 text-sm text-jade-deep hover:border-jade"
          >
            应收 / 到账明细
          </Link>
          <Link
            href="/portfolio"
            className="rounded-sm border border-line bg-surface px-3 py-2 text-sm text-ink-soft hover:border-ink"
          >
            返回持仓
          </Link>
        </div>
      </div>

      {error ? <p className="text-sm text-loss">{error}</p> : null}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["今年已到账", data?.summary.received],
          ["今年正式待收", data?.summary.pending],
          ["预案参考", data?.summary.proposal],
          ["全部待收", data?.summary.contract_pending],
        ].map(([label, value]) => (
          <div key={label} className="card p-5">
            <p className="text-xs text-muted">{label}</p>
            <p className="tnum mt-2 text-2xl font-semibold text-ink">
              {money(value)}
            </p>
          </div>
        ))}
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-medium text-ink">下笔预计到账</h2>
            <p className="mt-1 text-xs text-muted">只统计正式实施且有派息日的应收。</p>
          </div>
          {data?.summary.next_payment ? (
            <p className="tnum text-sm text-jade-deep">
              {data.summary.next_payment.payment_date} · {data.summary.next_payment.code} ·{" "}
              {money(data.summary.next_payment.amount)}
            </p>
          ) : (
            <p className="text-sm text-muted">暂无</p>
          )}
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-medium text-ink">月度现金流</h2>
        <p className="mt-1 text-xs text-muted">
          已到账按实际入账日；待收按正式派息日；预案按公告日期，不承诺发生。
        </p>
        <div className="mt-5 grid grid-cols-12 items-end gap-1 sm:gap-2">
          {data?.monthly.map((row) => {
            const label = row.month.slice(5);
            const received = Number(row.received);
            const pending = Number(row.pending);
            const proposal = Number(row.proposal);
            return (
              <button
                key={row.month}
                type="button"
                onClick={() => {
                  setMonth(Number(label));
                  setSelected(null);
                }}
                className="group flex min-w-0 flex-col items-center gap-1"
                title={`${row.month} 已收 ${row.received} / 待收 ${row.pending} / 预案 ${row.proposal}`}
              >
                <div className="flex h-28 w-full items-end justify-center gap-0.5">
                  <span
                    className="w-1/3 rounded-t-sm bg-jade"
                    style={{ height: `${(received / maxMonthly) * 100}%` }}
                  />
                  <span
                    className="w-1/3 rounded-t-sm bg-amber"
                    style={{ height: `${(pending / maxMonthly) * 100}%` }}
                  />
                  <span
                    className="w-1/3 rounded-t-sm bg-line"
                    style={{ height: `${(proposal / maxMonthly) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted">{label}</span>
              </button>
            );
          })}
        </div>
        <div className="mt-3 flex gap-4 text-[11px] text-muted">
          <span><i className="mr-1 inline-block h-2 w-2 bg-jade" />已收</span>
          <span><i className="mr-1 inline-block h-2 w-2 bg-amber" />待收</span>
          <span><i className="mr-1 inline-block h-2 w-2 bg-line" />预案</span>
        </div>
      </section>

      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
          <div>
            <h2 className="text-sm font-medium text-ink">分红日历</h2>
            <p className="mt-1 text-xs text-muted">{year} 年 · 登记 / 除息 / 派息 / 到账</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                if (month === 1) {
                  setYear((value) => value - 1);
                  setMonth(12);
                } else {
                  setMonth((value) => value - 1);
                }
              }}
              className="rounded-sm border border-line px-2 py-1 text-xs"
            >
              上月
            </button>
            <span className="tnum min-w-16 text-center text-sm">{monthPrefix}</span>
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                if (month === 12) {
                  setYear((value) => value + 1);
                  setMonth(1);
                } else {
                  setMonth((value) => value + 1);
                }
              }}
              className="rounded-sm border border-line px-2 py-1 text-xs"
            >
              下月
            </button>
          </div>
        </div>
        <div className="grid grid-cols-7 border-b border-line bg-[#faf9f5] text-center text-[11px] text-muted">
          {["日", "一", "二", "三", "四", "五", "六"].map((day) => (
            <span key={day} className="py-2">{day}</span>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {monthDays(year, month).map((day, index) => {
            if (!day) return <div key={`empty-${index}`} className="min-h-16 border-b border-r border-line/60" />;
            const items = byDate.get(day) ?? [];
            const active = selected === day;
            return (
              <button
                key={day}
                type="button"
                onClick={() => setSelected(day)}
                className={`min-h-16 border-b border-r border-line/60 p-1 text-left align-top ${
                  active ? "bg-jade-soft/50" : "hover:bg-black/[0.02]"
                }`}
              >
                <span className="tnum text-[11px] text-muted">{Number(day.slice(-2))}</span>
                <span className="mt-1 flex flex-wrap gap-0.5">
                  {items.slice(0, 3).map((item, itemIndex) => (
                    <i
                      key={`${item.code}-${item.date_type}-${itemIndex}`}
                      className={`h-1.5 w-1.5 rounded-full ${
                        item.date_type === "received"
                          ? "bg-jade"
                          : item.date_type === "payment"
                          ? "bg-amber"
                          : "bg-line"
                      }`}
                    />
                  ))}
                </span>
              </button>
            );
          })}
        </div>
        <div className="divide-y divide-line">
          {(selected ? byDate.get(selected) ?? [] : []).map((item, index) => (
            <div key={`${item.code}-${index}`} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <div>
                <p className="text-sm text-ink">
                  {item.code} · {item.date_type_label}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {item.plan || "—"}
                  {item.amount ? ` · ${money(item.amount)}` : ""}
                </p>
              </div>
              <span className="text-xs text-jade-deep">{STATUS[item.stage] ?? item.stage}</span>
            </div>
          ))}
          {selected && (byDate.get(selected)?.length ?? 0) === 0 ? (
            <p className="px-4 py-4 text-xs text-muted">当天没有分红事件。</p>
          ) : null}
          {!selected ? (
            <p className="px-4 py-4 text-xs text-muted">点击日期查看登记、除息、派息和到账记录。</p>
          ) : null}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card overflow-hidden">
          <div className="border-b border-line px-4 py-3">
            <h2 className="text-sm font-medium text-ink">日期未知 / 待核对</h2>
            <p className="mt-1 text-xs text-muted">
              缺登记日、派息日或计算依据的应收不进入正式日历。
            </p>
          </div>
          {(data?.unknown.length ?? 0) > 0 ? (
            <div className="divide-y divide-line">
              {data?.unknown.map((row) => (
                <div key={`${row.code}-${row.plan}`} className="px-4 py-3">
                  <p className="text-sm text-ink">{row.code}</p>
                  <p className="mt-1 text-xs text-muted">{row.plan || row.reason || "待核对"}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="p-5 text-sm text-muted">没有待核对日期。</p>
          )}
        </div>

        <div className="card overflow-hidden">
          <div className="border-b border-line px-4 py-3">
            <h2 className="text-sm font-medium text-ink">应收进度</h2>
          </div>
          {(data?.entitlements.length ?? 0) > 0 ? (
            <div className="divide-y divide-line">
              {data?.entitlements.slice(0, 8).map((row) => (
                <div key={row.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div>
                    <p className="text-sm text-ink">{row.code} · 登记 {row.record_date}</p>
                    <p className="tnum mt-1 text-xs text-muted">
                      已收 {money(row.received_amount)} / 应收 {money(row.gross_amount)}
                    </p>
                  </div>
                  <span className={row.status === "settled" ? "text-xs text-jade-deep" : "text-xs text-amber"}>
                    {STATUS[row.status] ?? row.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="p-5 text-sm text-muted">还没有正式应收。</p>
          )}
        </div>
      </section>
    </div>
  );
}
