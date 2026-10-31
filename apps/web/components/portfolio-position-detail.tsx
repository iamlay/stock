"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PortfolioPositionEvidence } from "@/components/portfolio-position-evidence";
import {
  amount,
  basisLabels,
  type Position,
  type Entry,
  type Kind,
} from "@/lib/portfolio-positions";
import {
  displayMoney,
  displayNumber,
  displayQuantity,
  displayPercent,
  shortBasis,
} from "@/lib/portfolio-display";
import { portfolioRequest } from "@/lib/portfolio";

type IncomeSnapshot = {
  receipts: {
    code: string;
    net_amount: string;
    status: string;
  }[];
};

const card = "min-w-0 rounded-2xl border border-line/50 bg-surface p-5 sm:p-6";
const button =
  "rounded-xl border border-line px-4 py-2.5 text-sm hover:border-jade disabled:opacity-50";
export function PortfolioPositionDetail({
  position: p,
  entries,
  canWrite,
  onEdit,
  accountId,
}: {
  position: Position;
  entries: Entry[];
  canWrite: boolean;
  onEdit: (kind: Kind, p: Position, entry?: Entry) => void;
  accountId: string;
}) {
  const [income, setIncome] = useState<IncomeSnapshot | null>(null);
  useEffect(() => {
    let active = true;
    portfolioRequest<IncomeSnapshot>(`/accounts/${accountId}/income`)
      .then((value) => {
        if (active) setIncome(value);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [accountId]);
  const cost =
    p.preferences.basis === "unknown" ? null : p.costs[p.preferences.basis];
  const closed = /^0(?:\.0+)?$/.test(p.quantity);
  const quoteTime = p.quote
    ? new Date(p.quote.at).toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
      })
    : null;
  const received = income
    ? income.receipts
        .filter((row) => row.code === p.code && row.status === "active")
        .reduce((sum, row) => sum + Number(row.net_amount), 0)
    : null;
  const netInvested =
    p.costs.net.total == null ? null : Number(p.costs.net.total);
  const payback =
    received != null && netInvested != null && netInvested > 0
      ? Math.min(100, Math.max(0, (received / netInvested) * 100))
      : null;
  const remaining =
    received != null && netInvested != null
      ? Math.max(netInvested - received, 0)
      : null;
  const annual = p.forecast.annual_amount == null ? null : Number(p.forecast.annual_amount);
  const paybackYears =
    remaining != null && annual != null && annual > 0
      ? remaining / annual
      : null;
  return (
    <div className="space-y-4" data-testid="position-detail">
      <header className="flex flex-wrap items-center justify-between gap-4 py-2">
        <div>
          <h1 className="text-2xl font-semibold sm:text-3xl">
            <span className="mr-2 text-lg text-muted">{p.code}</span>
            {p.name}
          </h1>
          <p className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
            <span className="rounded bg-jade-soft px-2 py-1 text-jade-deep">
              A股
            </span>
            <span className="rounded bg-surface px-2 py-1">人民币资产</span>
            <span className="px-2 py-1">
              {p.preferences.group || "未分组"}
              {closed ? " · 已清仓" : ""}
            </span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className={`${button} bg-ink text-paper`}
            disabled={!canWrite}
            onClick={() => onEdit("buy", p)}
          >
            买入
          </button>
          <button
            className={button}
            disabled={!canWrite || closed}
            onClick={() => onEdit("sell", p)}
          >
            卖出
          </button>
          <button
            className={button}
            disabled={!canWrite}
            onClick={() => onEdit("bonus", p)}
          >
            送股
          </button>
          <button
            className={button}
            disabled={!canWrite}
            onClick={() => onEdit("reinvest", p)}
          >
            分红复投
          </button>
        </div>
      </header>
      <section className="rounded-2xl border border-jade/20 bg-jade-soft p-5 sm:p-7">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-medium text-jade-deep">年度分红参考</h2>
          <button
            className="text-xs text-jade-deep underline underline-offset-4 disabled:opacity-50"
            disabled={!canWrite}
            onClick={() => onEdit("preference", p)}
          >
            调整参考
          </button>
        </div>
        <p
          data-testid="position-annual-reference"
          className="mt-4 break-all text-4xl font-semibold tabular-nums text-jade-deep"
        >
          {displayMoney(p.forecast.annual_amount)}
        </p>
        <p className="mt-3 text-sm text-jade-deep">
          {p.forecast.annual_per_share == null
            ? p.forecast.reason_label || "分红参考待补齐"
            : `每股 ${displayMoney(p.forecast.annual_per_share)} × ${displayQuantity(p.quantity)} 股 · 税前`}
        </p>
        <p className="mt-2 text-xs leading-6 text-muted">
          {p.forecast.status === "user_estimate"
            ? "自定义年度参考"
            : p.forecast.status === "historical_reference"
              ? `已收录历史参考 · 过去${p.forecast.window}个月`
              : "可在分红参考设置中调整"}
          ，不代表未来派息或实际到账。
        </p>
      </section>
      <section
        className={`${card} flex flex-wrap items-center justify-between gap-3`}
      >
        <div>
          <h2 className="text-sm text-muted">当前市值</h2>
          <p
            data-testid="position-market-value"
            className="mt-2 break-all text-3xl font-semibold tabular-nums"
          >
            {displayMoney(p.market_value)}
          </p>
        </div>
        <div className="text-sm sm:text-right">
          <p className="text-xs text-muted">
            {p.quote
              ? `${p.quote.time_label || "报价时间"} · ${quoteTime}`
              : "暂无有效报价"}
          </p>
          <p className="mt-2">
            {p.quote
              ? `${displayMoney(p.quote.price)} × ${displayQuantity(p.quantity)} 股`
              : "有有效报价后计算市值"}
          </p>
        </div>
      </section>
      <div className="grid grid-cols-2 gap-3 sm:gap-4">
        <section className={card}>
          <h2 className="text-sm text-muted">加权成本息率</h2>
          <p className="mt-3 break-all text-2xl font-semibold tabular-nums">
            {displayPercent(p.cost_yield)}
          </p>
          <p className="mt-2 text-xs leading-5 text-muted">
            {p.cost_yield == null
              ? "需有效分红参考及大于0的加权成本"
              : `按加权成本 ${displayMoney(p.costs.weighted.per_share)} /股计算`}
          </p>
        </section>
        <section className={card}>
          <h2 className="text-sm text-muted">股价息率</h2>
          <p
            data-testid="position-price-yield"
            className="mt-3 break-all text-2xl font-semibold tabular-nums text-jade-deep"
          >
            {displayPercent(p.price_yield)}
          </p>
          <p className="mt-2 text-xs leading-5 text-muted">
            {p.price_yield == null
              ? p.price_yield_issues?.join("；") || "分红参考或报价待补齐"
              : "年度每股分红参考 ÷ 当前报价"}
          </p>
        </section>
        <section className={card}>
          <h2 className="text-sm text-muted">持仓数量</h2>
          <p className="mt-3 break-all text-2xl font-semibold tabular-nums">
            {displayQuantity(p.quantity)}
            <span className="ml-1 text-sm font-normal">股</span>
          </p>
        </section>
        <section className={card}>
          <h2 className="text-sm text-muted">当前成本</h2>
          <p className="mt-3 break-all text-2xl font-semibold tabular-nums">
            {cost?.per_share == null
              ? "—"
              : `¥${displayNumber(cost.per_share, 4)}`}
          </p>
          <p className="mt-2 text-xs text-jade-deep">
            {shortBasis[p.preferences.basis]} · 元/股
          </p>
        </section>
      </div>
      {cost?.total != null &&
      p.preferences.basis !== "weighted" &&
      Number(cost.total) <= 0 ? (
        <p className="text-sm text-jade-deep">
          所选口径下净投入已回收，不再计算负分母股息率。
        </p>
      ) : null}
      <section
        className={`${card} flex flex-wrap justify-between gap-2 text-sm`}
      >
        <h2 className="text-muted">记账起点</h2>
        <p>
          {p.known_since}
          {p.date_semantics === "end_of_day" ? " · 日终快照" : " · 原记录日期"}
        </p>
        <p className="w-full text-xs leading-6 text-muted">
          起点前的持仓历史未知，不作为首次买入日期或完整持股天数。
          {p.estimated ? "含未知费用，成本及盈亏为估算。" : ""}
          {p.history_status === "incomplete"
            ? "期间记录仍有缺失，请补充核对。"
            : ""}
        </p>
      </section>
      <section className={card}>
        <div className="flex justify-between gap-3">
          <h2 className="text-sm text-muted">累计已获分红</h2>
          <strong className="text-xl text-amber">
            {received == null ? "—" : displayMoney(String(received))}
          </strong>
        </div>
        <p className="mt-2 text-xs text-muted">
          {received == null
            ? "收息数据暂不可用；未知金额不计作0。"
            : "来自本账本已确认的实际到账记录，按净额统计。"}
        </p>
      </section>
      <section className={card}>
        <div className="flex justify-between gap-3">
          <h2 className="font-medium">分红回本进度</h2>
          <span className="text-xl font-semibold text-amber">
            {payback == null ? "—" : `${payback.toFixed(1)}%`}
          </span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-line/50">
          <div
            className="h-full rounded-full bg-amber"
            style={{ width: `${payback ?? 0}%` }}
          />
        </div>
        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted">净投入</dt>
            <dd className="tnum">
              {netInvested == null ? "—" : displayMoney(String(netInvested))}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted">已收回分红</dt>
            <dd className="tnum text-amber">
              {received == null ? "—" : displayMoney(String(received))}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted">剩余待回收</dt>
            <dd className="tnum">
              {remaining == null ? "—" : displayMoney(String(remaining))}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted">按当前年度分红参考预计回本</dt>
            <dd className="tnum">
              {paybackYears == null ? "—" : `${paybackYears.toFixed(1)} 年`}
            </dd>
          </div>
        </dl>
        <p className="mt-3 text-xs leading-6 text-muted">
          净投入为“摊薄成本”口径，不是累计买入金额；预计回本按当前年度分红参考静态推算，
          不保证未来派息，也不构成收益承诺。
        </p>
      </section>
      <section className="overflow-hidden rounded-2xl border border-line/50 bg-surface">
        <div className="flex items-center justify-between gap-3 border-b border-line/50 p-5">
          <Link href={`/portfolio/${p.code}/transactions`} className="min-w-0">
            <span>
              交易明细
              <span className="mt-1 block text-xs text-muted">
                支持买入、卖出、送股、分红复投等记录
              </span>
            </span>
          </Link>
          <Link
            href={`/portfolio/${p.code}/transactions`}
            className="shrink-0 rounded-full bg-ink px-3 py-1 text-xs text-paper"
          >
            + 添加
          </Link>
        </div>
        <Link
          href="/portfolio/income"
          className="flex items-center justify-between gap-3 border-b border-line/50 p-5"
        >
          <span>
            分红记录
            <span className="mt-1 block text-xs text-muted">
              累计已获 {received == null ? "—" : displayMoney(String(received))}
            </span>
          </span>
          <span className="text-sm text-muted">查看 / 添加 ›</span>
        </Link>
        <div className="flex items-center justify-between gap-3 border-b border-line/50 p-5 text-muted">
          <span>
            历史分红回溯
            <span className="mt-1 block text-xs">
              按年回填历史分红记录，当前版本暂未开放
            </span>
          </span>
          <span className="text-xs">待开发</span>
        </div>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 border-b border-line/50 p-5 text-left disabled:opacity-50"
          disabled={!canWrite}
          onClick={() => onEdit("rebase", p)}
        >
          <span>
            编辑持仓
            <span className="mt-1 block text-xs text-muted">
              修正数量与{basisLabels[p.preferences.basis]}
            </span>
          </span>
          <span aria-hidden="true">›</span>
        </button>
        <a
          href={`/stocks/${p.code}?tab=dividend`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between gap-3 border-b border-line/50 p-5"
        >
          <span>
            分红档案
            <span className="mt-1 block text-xs text-muted">
              查看股票公开分红资料
            </span>
          </span>
          <span aria-hidden="true">↗</span>
        </a>
        <div className="flex items-center justify-between gap-3 p-5 text-muted">
          <span>
            删除持仓
            <span className="mt-1 block text-xs">
              删除会移除流水与关联记录，当前版本暂未开放
            </span>
          </span>
          <span className="text-xs">待开发</span>
        </div>
      </section>
      <section className={card}>
        <PortfolioPositionEvidence position={p} />
      </section>
      <p className="text-center text-xs leading-6 text-muted">
        每5分钟自动刷新 · 编辑时暂停
        <br />
        交易明细已集中展示；分红记录与历史回溯后续补充。
      </p>
      {p.reference != null ? (
        <p className="text-xs text-muted">
          原始未知口径参考总额 {amount(p.reference)} 元，不作为盈亏依据。
        </p>
      ) : null}
    </div>
  );
}
