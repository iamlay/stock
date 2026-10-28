"use client";

import { useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/auth";
import {
  portfolioRequest,
  PortfolioRequestError,
  type PortfolioAccount,
  type PortfolioPolicy,
} from "@/lib/portfolio";
import {
  amount,
  basisLabels,
  kindLabels,
  type Entry,
  type Holdings,
  type Kind,
  type Position,
} from "@/lib/portfolio-positions";
import { PortfolioPositionForm } from "@/components/portfolio-position-form";

const button =
  "rounded-lg border border-line px-4 py-2 text-sm disabled:opacity-50 hover:border-jade";
function sourceLink(url: string | null) {
  try {
    const u = new URL(url ?? "");
    return ["https:", "http:"].includes(u.protocol) ? u.href : undefined;
  } catch {
    return undefined;
  }
}
export function PortfolioLedger({
  account,
  policy,
  refresh,
  authFailure,
}: {
  account: PortfolioAccount;
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
  useEffect(() => {
    alive.current = true;
    token.current = getToken();
    void portfolioRequest<Holdings>(`/accounts/${account.id}/holdings`)
      .then((result) => {
        if (current()) setData(result);
      })
      .catch((err) => {
        if (!current()) return;
        if (err instanceof PortfolioRequestError && err.status === 401)
          authFailure(err);
        else
          setError(
            err instanceof Error ? err.message : "持仓暂时无法读取，请刷新。",
          );
      });
    return () => {
      alive.current = false;
    };
  }, [account.id, authFailure]);
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
        onCancel={() => setEditing(null)}
        onError={(err) => {
          if (err instanceof PortfolioRequestError && err.status === 401)
            authFailure(err);
        }}
        onSaved={(result) => {
          setData(result);
          setEditing(null);
          refresh("持仓已保存，可继续添加下一只股票。");
        }}
      />
    );
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-serif text-2xl">我的持仓</h2>
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
          <div className="rounded-xl bg-ink p-5 text-paper">
            <p className="text-sm opacity-80">已知行情对应市值</p>
            <strong className="mt-2 block break-all text-3xl">
              ¥ {amount(data.known_market_value)}
            </strong>
            <p className="mt-2 text-xs opacity-80">
              {data.missing_quotes
                ? `${data.missing_quotes}只持仓缺报价，未计入此金额。`
                : "报价时点见各持仓，不代表实时成交价。"}{" "}
              起点前收益未知，实际分红到账尚未开放。
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
            positions.map((p) => {
              const basis = p.preferences.basis;
              const cost = basis === "unknown" ? null : p.costs[basis];
              return (
                <article
                  key={p.code}
                  className="card space-y-4 rounded-xl p-5 sm:p-6"
                >
                  <div className="flex flex-wrap justify-between gap-3">
                    <div>
                      <h3 className="font-medium">
                        {p.name}{" "}
                        <span className="ml-2 text-xs text-muted">A股</span>
                      </h3>
                      <p className="mt-1 text-sm text-muted">
                        {p.code} · {p.preferences.group || "未分组"}
                      </p>
                    </div>
                    <div className="text-sm">
                      <p className="text-xs text-muted">年度分红参考 · 税前</p>
                      <strong className="mt-1 block text-lg text-jade-deep">
                        {p.forecast.annual_amount === null
                          ? p.forecast.status === "not_set"
                            ? "未设置"
                            : "资料不足"
                          : `¥ ${amount(p.forecast.annual_amount)}`}
                      </strong>
                    </div>
                  </div>
                  <dl className="grid grid-cols-2 gap-4 rounded-lg bg-paper p-4 sm:grid-cols-4">
                    {[
                      ["持仓（股）", p.quantity],
                      ["市值（元）", p.market_value],
                      [`${basisLabels[basis]}（元/股）`, cost?.per_share],
                      ["当前价格股息率（%）", p.price_yield],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <dt className="text-xs text-muted">{label}</dt>
                        <dd className="mt-2 break-all font-medium tabular-nums">
                          {amount(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {cost?.total &&
                  basis !== "weighted" &&
                  Number(cost.total) <= 0 ? (
                    <p className="text-sm text-jade-deep">
                      所选口径下净投入已回收，不再计算负分母股息率。
                    </p>
                  ) : null}
                  {p.reference !== null ? (
                    <p className="text-xs text-muted">
                      原始未知口径参考总额：{amount(p.reference)}{" "}
                      元，不作为当前每股成本或盈亏依据。
                    </p>
                  ) : null}
                  <p className="text-xs leading-6 text-muted">
                    {p.quote
                      ? `报价 ¥${amount(p.quote.price)} · ${new Date(p.quote.at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })}`
                      : "暂无可用报价"}
                    。历史起点 {p.known_since}
                    {p.date_semantics === "end_of_day"
                      ? "（日终快照）"
                      : "（原记录语义）"}
                    ；此前未知。
                    {p.history_status === "incomplete" ? "期间记录仍有缺失，显示值仅根据已录入资料计算，请补充核对。" : ""}
                    {p.estimated ? "含未知费用，成本及盈亏为估算。" : ""}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className={button}
                      disabled={!canWrite}
                      onClick={() => open("buy", p)}
                    >
                      买入
                    </button>
                    <button
                      type="button"
                      className={button}
                      disabled={!canWrite || /^0(?:\.0+)?$/.test(p.quantity)}
                      onClick={() => open("sell", p)}
                    >
                      卖出
                    </button>
                    <button
                      type="button"
                      className={button}
                      disabled={!canWrite}
                      onClick={() => open("rebase", p)}
                    >
                      修正当前持仓
                    </button>
                    <button
                      type="button"
                      className={button}
                      disabled={!canWrite}
                      onClick={() => open("preference", p)}
                    >
                      分组与分红参考
                    </button>
                    <a
                      href={`/stocks/${p.code}?tab=dividend`}
                      target="_blank"
                      rel="noreferrer"
                      className={button}
                    >
                      分红档案 ↗
                    </a>
                  </div>
                  <details>
                    <summary className="cursor-pointer text-sm text-jade-deep">
                      成本明细、分红依据与交易记录
                    </summary>
                    <div className="mt-4 space-y-4">
                      <dl className="grid gap-3 sm:grid-cols-3">
                        {(["weighted", "net", "dividend"] as const).map((b) => (
                          <div
                            key={b}
                            className="rounded-lg border border-line p-3 text-sm"
                          >
                            <dt>{basisLabels[b]}</dt>
                            <dd className="mt-2">
                              {p.costs[b].per_share === null
                                ? "资料不足 / 已清仓"
                                : `${amount(p.costs[b].per_share)} 元/股`}
                            </dd>
                            <dd className="mt-1 text-xs text-muted">
                              总额 {amount(p.costs[b].total)} 元
                            </dd>
                          </div>
                        ))}
                      </dl>
                      <p className="text-sm">
                        当前周期记账起点后交易盈亏：{amount(p.realized_pnl)}{" "}
                        元。加权成本股息率：{amount(p.cost_yield)}%。
                      </p>
                      {p.closed_cycles.length ? (
                        <details>
                          <summary className="cursor-pointer text-sm">
                            此前记账区间（{p.closed_cycles.length}）
                          </summary>
                          {p.closed_cycles.map((c) => (
                            <p
                              className="mt-2 text-xs text-muted"
                              key={c.cycle_id}
                            >
                              该区间已记录交易盈亏 {amount(c.realized_pnl)}{" "}
                              元；不抵减新周期成本。
                            </p>
                          ))}
                        </details>
                      ) : null}
                      <p className="text-xs leading-6 text-muted">
                        {p.forecast.note}。明细窗口：({p.forecast.from_date},{" "}
                        {p.forecast.to_date}]；日期缺失的记录单独待核对。
                      </p>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-line">
                              <th className="p-2 whitespace-nowrap">
                                报告期 / 除息日
                              </th>
                              <th className="p-2 whitespace-nowrap">
                                每股现金（元）
                              </th>
                              <th className="p-2 whitespace-nowrap">
                                阶段 / 来源
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {p.forecast.details.map((d) => (
                              <tr
                                key={d.event_id}
                                className="border-b border-line"
                              >
                                <td className="p-2 whitespace-nowrap">
                                  {d.report_date || "未知"}
                                  <br />
                                  {d.ex_date || "待核对"}
                                </td>
                                <td className="p-2">
                                  {amount(d.cash_per_share)}
                                </td>
                                <td className="p-2">
                                  {d.stage === "implemented"
                                    ? "已实施"
                                    : d.stage === "proposal"
                                      ? "预案"
                                      : "待核对"}
                                  <br />
                                  {sourceLink(d.source_url) ? (
                                    <a
                                      href={sourceLink(d.source_url)}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="underline"
                                    >
                                      {d.source}
                                    </a>
                                  ) : (
                                    d.source
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!p.forecast.details.length ? (
                          <p className="py-3 text-xs text-muted">
                            没有可展示的窗口内记录；不代表确认无分红。
                          </p>
                        ) : null}
                      </div>
                      <div className="space-y-3">
                        {data.entries
                          .filter((e) => e.code === p.code)
                          .map((e) => (
                            <div
                              key={e.id}
                              className="border-t border-line pt-3 text-xs leading-6"
                            >
                              <p>
                                {e.event_date} · {kindLabels[e.kind]} · 当天顺序{" "}
                                {e.day_order} ·{" "}
                                {e.active ? "有效" : "已撤销 / 更正凭据"}
                              </p>
                              {!["preference", "reversal"].includes(e.kind) ? (
                                <p>
                                  数量 {amount(e.quantity)} ·{" "}
                                  {["snapshot", "rebase"].includes(e.kind)
                                    ? `${basisLabels[e.details?.basis ?? "unknown"]} 总额 ${amount(e.details?.amount)}`
                                    : `价格 ${amount(e.price)} · 费用 ${amount(e.fees)}${e.details?.fees_known === false ? "（未知，暂按0）" : ""}`}
                                  {["opening", "adjustment"].includes(e.kind)
                                    ? ` · 原总成本 ${amount(e.total_cost)}`
                                    : ""}
                                </p>
                              ) : null}
                              {e.note ? (
                                <p className="break-all">原因：{e.note}</p>
                              ) : null}
                              {e.evidence ? (
                                <p className="break-all">依据：{e.evidence}</p>
                              ) : null}
                              {e.active &&
                              !["preference", "reversal"].includes(e.kind) ? (
                                <div className="mt-2 flex gap-2">
                                  <button
                                    type="button"
                                    className={button}
                                    disabled={!canWrite}
                                    onClick={() => open(e.kind, p, e)}
                                  >
                                    更正
                                  </button>
                                  <button
                                    type="button"
                                    className={button}
                                    disabled={!canWrite}
                                    onClick={() => open("reversal", p, e)}
                                  >
                                    撤销
                                  </button>
                                </div>
                              ) : null}
                            </div>
                          ))}
                      </div>
                    </div>
                  </details>
                </article>
              );
            })
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
