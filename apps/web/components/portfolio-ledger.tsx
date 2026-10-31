"use client";

import Link from "next/link";
import { PortfolioPositionDetail } from "@/components/portfolio-position-detail";
import { PortfolioTransactions } from "@/components/portfolio-transactions";
import {
  displayNumber,
  displayQuantity,
  displayMoney,
  displayPercent,
  shortBasis,
} from "@/lib/portfolio-display";
import { useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/auth";
import {
  portfolioRequest,
  PortfolioRequestError,
  type PortfolioAccount,
  type PortfolioPolicy,
} from "@/lib/portfolio";
import {
  kindLabels,
  type Entry,
  type Holdings,
  type Kind,
  type Position,
} from "@/lib/portfolio-positions";
import { PortfolioPositionForm } from "@/components/portfolio-position-form";

const button =
  "rounded-lg border border-line px-4 py-2 text-sm disabled:opacity-50 hover:border-jade";
export function PortfolioLedger({
  account,
  selectedCode,
  initialView = "detail",
  policy,
  refresh,
  authFailure,
}: {
  account: PortfolioAccount;
  selectedCode?: string;
  initialView?: "detail" | "transactions";
  policy: PortfolioPolicy | null;
  refresh: (message?: string) => void;
  authFailure: (error: unknown) => void;
}) {
  const [data, setData] = useState<Holdings | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [group, setGroup] = useState("");
  const [sort, setSort] = useState("name");
  const [closed, setClosed] = useState(false);
  const [editing, setEditing] = useState<{
    id: string;
    kind: Kind;
    position?: Position;
    correction?: Entry;
  } | null>(null);
  const alive = useRef(false);
  const token = useRef(getToken());
  const current = () => alive.current && token.current === getToken();
  const isEditing = editing !== null;
  useEffect(() => {
    alive.current = true;
    token.current = getToken();
    if (isEditing)
      return () => {
        alive.current = false;
      };
    let stopped = false;
    let inFlight = false;
    let lastAttempt = 0;
    let controller: AbortController | null = null;
    const intervalMs = 5 * 60 * 1000;
    const readHoldings = async () => {
      if (
        stopped ||
        inFlight ||
        !current() ||
        document.visibilityState === "hidden"
      )
        return;
      inFlight = true;
      lastAttempt = Date.now();
      controller = new AbortController();
      const requestController = controller;
      const timeout = window.setTimeout(
        () => requestController.abort(),
        30_000,
      );
      try {
        const result = await portfolioRequest<Holdings>(
          `/accounts/${account.id}/holdings`,
          {
            signal: controller.signal,
          },
        );
        if (!stopped && current()) {
          setData(result);
          setError("");
        }
      } catch (err) {
        if (stopped || !current()) return;
        if (err instanceof PortfolioRequestError && err.status === 401) {
          stopped = true;
          authFailure(err);
        } else {
          setError(
            "持仓刷新失败，已保留上次数据；稍后自动重试，也可点击刷新。",
          );
        }
      } finally {
        window.clearTimeout(timeout);
        inFlight = false;
      }
    };
    const refreshIfDue = () => {
      if (Date.now() - lastAttempt >= intervalMs) void readHoldings();
    };
    void readHoldings();
    const timer = window.setInterval(() => void readHoldings(), intervalMs);
    document.addEventListener("visibilitychange", refreshIfDue);
    window.addEventListener("focus", refreshIfDue);
    return () => {
      stopped = true;
      alive.current = false;
      controller?.abort();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshIfDue);
      window.removeEventListener("focus", refreshIfDue);
    };
  }, [account.id, authFailure, isEditing]);
  async function accept() {
    if (!data || !policy || !accepted || busy || !current()) return;
    setBusy(true);
    setError("");
    try {
      await portfolioRequest(`/accounts/${account.id}/consent`, {
        method: "POST",
        body: JSON.stringify({
          expected_version: data.account_version,
          consent: {
            accepted: true,
            version: policy.policy.version,
            sha256: policy.sha256,
          },
        }),
      });
      if (current()) refresh();
    } catch (err) {
      if (current()) {
        authFailure(err);
        setError(err instanceof Error ? err.message : "确认失败");
      }
    } finally {
      if (current()) setBusy(false);
    }
  }
  function open(kind: Kind, position?: Position, correction?: Entry) {
    setEditing({ id: crypto.randomUUID(), kind, position, correction });
    setMessage("");
    setError("");
  }
  const canWrite = !!data && !data.consent_required && !account.is_archived;
  const positions =
    data?.positions
      .filter(
        (p) =>
          (!group || (p.preferences.group || "未分组") === group) &&
          (closed || !/^0(?:\.0+)?$/.test(p.quantity)),
      )
      .sort((a, b) =>
        sort === "name"
          ? a.name.localeCompare(b.name, "zh")
          : sort === "code"
            ? a.code.localeCompare(b.code)
            : Number(b.market_value ?? -1) - Number(a.market_value ?? -1),
      ) ?? [];
  if (editing && data)
    return (
      <PortfolioPositionForm
        key={editing.id}
        accountId={account.id}
        version={data.account_version}
        positions={data.positions}
        initialKind={editing.kind}
        initialPosition={editing.position}
        correction={editing.correction}
        tradeTabs={initialView === "transactions" && !editing.correction}
        onCancel={() => setEditing(null)}
        onError={(err) => {
          if (err instanceof PortfolioRequestError && err.status === 401)
            authFailure(err);
        }}
        onSaved={(result) => {
          setData(result);
          setEditing(null);
          refresh(
            selectedCode
              ? "持仓已更新。"
              : "持仓已保存，可继续添加下一只股票。",
          );
        }}
      />
    );
  if (selectedCode) {
    const position = data?.positions.find((p) => p.code === selectedCode);
    if (initialView === "transactions") {
      return (
        <section className="space-y-4">
          <Link
            href={`/portfolio/${selectedCode}`}
            className="inline-flex py-2 text-sm text-jade-deep"
          >
            ← 返回持仓详情
          </Link>
          {error ? (
            <p role="alert" className="text-sm text-loss">
              {error}
            </p>
          ) : null}
          {!data ? (
            <p role="status">正在读取持仓…</p>
          ) : !position ? (
            <div className="card rounded-2xl p-8">
              当前账本中没有这只股票的持仓。请返回列表查看。
            </div>
          ) : (
            <>
              <div>
                <h1 className="font-serif text-2xl">交易明细</h1>
                <p className="mt-1 text-sm text-muted">
                  {position.code} {position.name} · 共{" "}
                  {data.entries.filter(
                    (entry) =>
                      entry.code === position.code && entry.kind !== "preference",
                  ).length}{" "}
                  笔
                </p>
              </div>
              <PortfolioTransactions
                position={position}
                entries={data.entries}
                canWrite={canWrite}
                onEdit={open}
                onAdd={() => open("buy", position)}
              />
            </>
          )}
        </section>
      );
    }
    return (
      <section className="space-y-4">
        <Link
          href="/portfolio"
          className="inline-flex py-2 text-sm text-jade-deep"
        >
          ← 返回我的持仓
        </Link>
        {error ? (
          <p role="alert" className="text-sm text-loss">
            {error}
          </p>
        ) : null}
        {!data ? (
          <p role="status">正在读取持仓…</p>
        ) : !position ? (
          <div className="card rounded-2xl p-8">
            当前账本中没有这只股票的持仓。请返回列表查看。
          </div>
        ) : (
          <>
            {data.consent_required ? (
              <p className="text-sm text-muted">
                请返回持仓列表确认新版数据说明后进行编辑。
              </p>
            ) : null}
            {account.is_archived ? (
              <p className="text-sm text-muted">账本已归档，返回列表可恢复。</p>
            ) : null}
            <PortfolioPositionDetail
              position={position}
              entries={data.entries}
              canWrite={canWrite}
              onEdit={open}
              accountId={account.id}
            />
          </>
        )}
      </section>
    );
  }
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-medium">股票资产</h2>
          <p className="mt-1 text-xs text-muted">
            {account.name} · 人民币 ·{" "}
            {data?.positions.filter((p) => !/^0(?:\.0+)?$/.test(p.quantity))
              .length ?? 0}
            只
          </p>
        </div>
        <button
          type="button"
          className={`${button} bg-jade text-white`}
          disabled={!canWrite}
          onClick={() => open("snapshot")}
        >
          ＋ 添加持仓
        </button>
      </div>
      {message ? (
        <p role="status" className="text-sm text-jade-deep">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-loss">
          {error}
        </p>
      ) : null}
      {!data ? (
        <p className="text-sm text-muted">正在读取持仓…</p>
      ) : (
        <>
          {data.consent_required ? (
            <div className="card space-y-3 p-5">
              <h3 className="font-medium">请确认新版持仓数据范围</h3>
              {policy ? (
                <>
                  <ul className="list-disc space-y-2 pl-5 text-sm leading-6">
                    {policy.policy.sections.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                  <a
                    className="text-sm text-jade-deep underline"
                    href={policy.policy.privacy_path}
                    target="_blank"
                    rel="noreferrer"
                  >
                    完整隐私政策
                  </a>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={accepted}
                      disabled={busy}
                      onChange={(e) => setAccepted(e.target.checked)}
                    />
                    我已阅读，自愿保存上述持仓与参考设置。
                  </label>
                  <button
                    type="button"
                    className={button}
                    disabled={!accepted || busy}
                    onClick={() => void accept()}
                  >
                    确认并启用新版录入
                  </button>
                </>
              ) : null}
            </div>
          ) : null}
          <div className="rounded-2xl bg-ink p-5 text-paper">
            <p className="text-sm opacity-80">已知行情对应市值</p>
            <strong className="mt-2 block break-all text-3xl">
              {displayMoney(data.known_market_value)}
            </strong>
            <p className="mt-2 text-xs opacity-80">
              {data.missing_quotes
                ? `${data.missing_quotes}只持仓缺报价，未计入此金额。`
                : "报价时点见各持仓，不代表实时成交价。"}{" "}
              每5分钟自动刷新 · 分红为年度参考，非实际到账。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>
              分组{" "}
              <select
                aria-label="筛选分组"
                className="rounded border border-line bg-surface p-2"
                value={group}
                onChange={(e) => setGroup(e.target.value)}
              >
                <option value="">全部</option>
                {Array.from(
                  new Set(
                    data.positions.map((p) => p.preferences.group || "未分组"),
                  ),
                )
                  .sort()
                  .map((g) => (
                    <option key={g}>{g}</option>
                  ))}
              </select>
            </label>
            <label>
              排序{" "}
              <select
                aria-label="排序"
                className="rounded border border-line bg-surface p-2"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
              >
                <option value="name">名称</option>
                <option value="code">代码</option>
                <option value="value">市值从高到低</option>
              </select>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={closed}
                onChange={(e) => setClosed(e.target.checked)}
              />
              显示已清仓
            </label>
          </div>
          {account.is_archived ? (
            <p className="text-sm text-muted">
              账本已归档，可在下方设置中恢复。
            </p>
          ) : null}
          {!positions.length ? (
            <div className="card p-8 text-center text-sm text-muted">
              {data.positions.length
                ? "当前筛选下没有持仓。"
                : "还没有持仓。按券商当前持仓录入，或记下一笔买入。"}
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {positions.map((p) => {
                const cost =
                  p.preferences.basis === "unknown"
                    ? null
                    : p.costs[p.preferences.basis].per_share;
                return (
                  <Link
                    key={p.code}
                    href={`/portfolio/${p.code}`}
                    aria-label={`查看${p.name}持仓详情`}
                    className="block min-w-0 rounded-2xl border border-line/60 bg-surface p-4 transition hover:border-jade/50 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-jade sm:p-5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 gap-3">
                        <span
                          aria-hidden="true"
                          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-paper font-serif text-xl"
                        >
                          {p.name.slice(0, 1)}
                        </span>
                        <div className="min-w-0">
                          <h3 className="break-words font-semibold">
                            {p.name}{" "}
                            <span className="rounded bg-jade-soft px-1 text-[10px] font-normal text-jade-deep">
                              A股
                            </span>
                          </h3>
                          <p className="mt-1 text-xs text-muted">
                            {p.code}
                            {/^0(?:\.0+)?$/.test(p.quantity) ? " · 已清仓" : ""}
                          </p>
                        </div>
                      </div>
                      <div className="max-w-[46%] shrink-0 text-right">
                        <strong className="block break-all text-lg tabular-nums text-jade-deep sm:text-xl">
                          {displayMoney(p.forecast.annual_amount, true)}
                        </strong>
                        <span className="text-[11px] text-muted">
                          年度分红参考
                        </span>
                      </div>
                    </div>
                    <dl className="mt-4 grid grid-cols-4 divide-x divide-line/60 rounded-xl bg-paper/80 py-3 text-center">
                      {[
                        ["持仓", displayQuantity(p.quantity), "股"],
                        ["市值", displayMoney(p.market_value, true), ""],
                        [
                          "成本/股",
                          cost == null ? "—" : `¥${displayNumber(cost, 4)}`,
                          "",
                        ],
                        ["股价息率", displayPercent(p.price_yield), ""],
                      ].map(([label, value, unit]) => (
                        <div key={label} className="min-w-0 px-1 sm:px-2">
                          <dt className="text-[11px] text-muted">{label}</dt>
                          <dd
                            className={`mt-1.5 break-all text-xs font-semibold tabular-nums sm:text-sm ${label === "股价息率" ? "text-jade-deep" : ""}`}
                          >
                            {value}
                            <span className="ml-0.5 text-[10px] font-normal">
                              {unit}
                            </span>
                          </dd>
                        </div>
                      ))}
                    </dl>
                    <p className="mt-3 flex flex-wrap justify-between gap-1 text-[11px] text-muted">
                      <span>
                        {shortBasis[p.preferences.basis]} ·{" "}
                        {p.preferences.group || "未分组"}
                      </span>
                      <span>
                        {p.forecast.annual_amount == null
                          ? "分红参考待设置或补齐"
                          : p.forecast.status === "user_estimate"
                            ? "自定义参考"
                            : "已收录历史参考"}{" "}
                        <span aria-hidden="true">›</span>
                      </span>
                    </p>
                  </Link>
                );
              })}
            </div>
          )}

          <details className="card p-5">
            <summary className="cursor-pointer text-sm">
              全部记录（含已撤销持仓）
            </summary>
            <div className="mt-3 space-y-2 text-xs text-muted">
              {data.entries.map((e) => (
                <p key={e.id}>
                  {e.code} · {e.event_date} · {kindLabels[e.kind]} ·{" "}
                  {e.active ? "有效" : "已撤销 / 更正凭据"}
                  {e.note ? ` · ${e.note}` : ""}
                </p>
              ))}
            </div>
          </details>
        </>
      )}
    </section>
  );
}
