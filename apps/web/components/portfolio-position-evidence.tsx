"use client";
import {
  amount,
  basisLabels,
  kindLabels,
  type Position,
  type Entry,
  type Kind,
} from "@/lib/portfolio-positions";
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
export function PortfolioPositionEvidence({
  position: p,
  entries,
  canWrite,
  onEdit: open,
}: {
  position: Position;
  entries: Entry[];
  canWrite: boolean;
  onEdit: (kind: Kind, p: Position, entry?: Entry) => void;
}) {
  return (
    <details>
      <summary className="cursor-pointer text-sm text-jade-deep">
        成本明细、分红依据与交易记录
      </summary>
      <div className="mt-4 space-y-4">
        <dl className="grid gap-3 sm:grid-cols-3">
          {(["weighted", "net", "dividend"] as const).map((b) => (
            <div key={b} className="rounded-lg border border-line p-3 text-sm">
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
              <p className="mt-2 text-xs text-muted" key={c.cycle_id}>
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
                <th className="p-2 whitespace-nowrap">报告期 / 除息日</th>
                <th className="p-2 whitespace-nowrap">每股现金（元）</th>
                <th className="p-2 whitespace-nowrap">阶段 / 来源</th>
              </tr>
            </thead>
            <tbody>
              {p.forecast.details.map((d) => (
                <tr key={d.event_id} className="border-b border-line">
                  <td className="p-2 whitespace-nowrap">
                    {d.report_date || "未知"}
                    <br />
                    {d.ex_date || "待核对"}
                  </td>
                  <td className="p-2">{amount(d.cash_per_share)}</td>
                  <td className="p-2">
                    {(
                      {
                        implemented: "已实施",
                        proposed: "预案",
                        approved: "已通过，未实施",
                        cancelled: "已取消",
                        no_distribution: "不分配",
                        historical: "历史记录",
                      } as Record<string, string>
                    )[d.stage] || "待核对"}
                    <p>
                      {d.included ? "计入参考" : d.exclusion_reason || "待核对"}
                    </p>
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
          {entries
            .filter((e) => e.code === p.code)
            .map((e) => (
              <div
                key={e.id}
                className="border-t border-line pt-3 text-xs leading-6"
              >
                <p>
                  {e.event_date} · {kindLabels[e.kind]} · 当天顺序 {e.day_order}{" "}
                  · {e.active ? "有效" : "已撤销 / 更正凭据"}
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
                {e.note ? <p className="break-all">原因：{e.note}</p> : null}
                {e.evidence ? (
                  <p className="break-all">依据：{e.evidence}</p>
                ) : null}
                {e.active && !["preference", "reversal"].includes(e.kind) ? (
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
  );
}
