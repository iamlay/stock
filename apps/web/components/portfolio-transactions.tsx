"use client";

import {
  amount,
  inputTotal,
  kindLabels,
  type Entry,
  type Kind,
  type Position,
} from "@/lib/portfolio-positions";

const badge: Record<string, string> = {
  buy: "bg-amber-soft text-amber",
  sell: "bg-jade-soft text-jade-deep",
  snapshot: "bg-line/40 text-ink-soft",
  rebase: "bg-line/40 text-ink-soft",
  opening: "bg-line/40 text-ink-soft",
  adjustment: "bg-loss/10 text-loss",
  bonus: "bg-jade-soft text-jade-deep",
  reinvest: "bg-jade-soft text-jade-deep",
  reversal: "bg-line/40 text-muted",
};

const PLUS = new Set<Kind>(["buy", "bonus", "reinvest"]);

function entryAmount(entry: Entry): string | null {
  if (["snapshot", "rebase", "opening", "adjustment"].includes(entry.kind)) {
    return entry.details?.amount ?? entry.total_cost;
  }
  if (entry.kind === "buy") {
    return inputTotal(entry.quantity, entry.price, entry.fees);
  }
  if (entry.kind === "sell") {
    return inputTotal(entry.quantity, entry.price, `-${entry.fees}`);
  }
  return null;
}

export function PortfolioTransactions({
  position,
  entries,
  canWrite,
  onEdit,
}: {
  position: Position;
  entries: Entry[];
  canWrite: boolean;
  onEdit: (kind: Kind, position: Position, entry?: Entry) => void;
}) {
  const rows = entries
    .filter((entry) => entry.code === position.code && entry.kind !== "preference")
    .sort((a, b) =>
      a.event_date === b.event_date
        ? b.day_order - a.day_order
        : b.event_date.localeCompare(a.event_date),
    );

  return (
    <section className="overflow-hidden rounded-2xl border border-line/50 bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line/50 px-5 py-4">
        <div>
          <h2 className="font-medium">交易明细</h2>
          <p className="mt-1 text-xs text-muted">共 {rows.length} 笔 · 点击编辑或撤销</p>
        </div>
      </div>
      {rows.length ? (
        <div className="divide-y divide-line/60">
          {rows.map((entry) => {
            const q = Number(entry.quantity);
            const total = entryAmount(entry);
            return (
              <div
                key={entry.id}
                className={`flex flex-wrap items-start justify-between gap-3 px-5 py-4 ${
                  entry.active ? "" : "opacity-60"
                }`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="tnum text-xs text-muted">{entry.event_date}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] ${
                        badge[entry.kind] ?? "bg-line/40 text-ink-soft"
                      }`}
                    >
                      {kindLabels[entry.kind]}
                    </span>
                    {!entry.active ? (
                      <span className="text-[11px] text-muted">已撤销 / 更正凭据</span>
                    ) : null}
                    {entry.day_order > 1 ? (
                      <span className="text-[11px] text-muted">顺序 {entry.day_order}</span>
                    ) : null}
                  </div>
                  <p className="tnum mt-2 text-lg font-medium text-ink">
                    {entry.kind === "reversal"
                      ? "—"
                      : `${PLUS.has(entry.kind) ? "+" : entry.kind === "sell" ? "-" : ""}${amount(
                          entry.quantity,
                        )} 股`}
                  </p>
                  <p className="tnum mt-1 text-xs text-muted">
                    {["snapshot", "rebase", "opening", "adjustment"].includes(entry.kind)
                      ? `成本 ${amount(total)} 元`
                      : entry.kind === "bonus"
                        ? "送股数量增加，总成本不变"
                        : entry.kind === "reinvest"
                          ? "分红复投，总成本不变"
                          : entry.kind === "buy"
                            ? `买入 ${amount(entry.price)} 元/股 · 支出 ${amount(total)} 元`
                            : entry.kind === "sell"
                              ? `卖出 ${amount(entry.price)} 元/股 · 净收入 ${amount(total)} 元`
                              : "撤销凭据"}
                  </p>
                  {entry.note ? (
                    <p className="mt-1 break-all text-xs text-muted">原因：{entry.note}</p>
                  ) : null}
                </div>
                {canWrite && entry.active && !["reversal"].includes(entry.kind) ? (
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      onClick={() => onEdit(entry.kind, position, entry)}
                      className="rounded-lg border border-line px-3 py-1.5 text-xs hover:border-jade"
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      onClick={() => onEdit("reversal", position, entry)}
                      className="rounded-lg border border-line px-3 py-1.5 text-xs text-loss hover:border-loss"
                    >
                      删除
                    </button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="px-5 py-6 text-sm text-muted">还没有交易记录。</p>
      )}
      <div className="border-t border-line/50 p-4">
        <button
          type="button"
          disabled={!canWrite}
          onClick={() => onEdit("buy", position)}
          className="w-full rounded-xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:opacity-50"
        >
          + 添加交易
        </button>
      </div>
    </section>
  );
}
