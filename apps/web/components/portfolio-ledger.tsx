"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { getToken } from "@/lib/auth";
import { portfolioRequest, PortfolioRequestError, type PortfolioAccount, type PortfolioPolicy } from "@/lib/portfolio";

const button = "rounded-sm border border-line px-4 py-2 text-sm disabled:opacity-50 hover:border-jade";
const input = "w-full min-w-0 rounded-sm border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-jade";
const labels: Record<string, string> = { opening: "期初持仓", buy: "买入", sell: "卖出", adjustment: "持仓调整", reversal: "冲正撤销" };
type Entry = {
  id: string; code: string; kind: string; event_date: string; day_order: number;
  quantity: string; price: string; fees: string; total_cost: string;
  history_status: string; note: string; evidence: string; active: boolean; reverses_id: string | null;
};
type Position = { code: string; quantity: string; total_cost: string; average_cost: string | null;
  realized_pnl: string; fees: string; known_since: string; history_status: string; has_adjustment: boolean };
type Ledger = { account_version: number; consent_required: boolean; entries: Entry[]; positions: Position[];
  review_ranges: { code: string; from_date: string; status: string }[] };
const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const empty = () => ({ code: "", kind: "opening", event_date: today(), day_order: "10", quantity: "", price: "0", fees: "0", total_cost: "", history_status: "since_date", note: "", evidence: "", reverses_id: null as string | null });
// Preserve decimal strings. Never convert portfolio amounts through JS Number.
const amount = (value: string | null) => value === null ? "—" : value.replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");

export function PortfolioLedger({ account, policy, refresh, authFailure }: {
  account: PortfolioAccount; policy: PortfolioPolicy | null; refresh: () => void; authFailure: (error: unknown) => void;
}) {
  const [data, setData] = useState<Ledger | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [form, setForm] = useState(empty);
  const alive = useRef(false);
  const token = useRef(getToken());
  const request = useRef<{ content: string; id: string } | null>(null);
  const current = () => alive.current && token.current === getToken();
  useEffect(() => {
    alive.current = true;
    token.current = getToken();
    void portfolioRequest<Ledger>(`/accounts/${account.id}/ledger`).then((result) => {
      if (current()) setData(result);
    }).catch((err) => {
      if (!current()) return;
      if (err instanceof PortfolioRequestError && err.status === 401) authFailure(err);
      else setError(err instanceof Error ? err.message : "流水暂时无法读取，请刷新。");
    });
    return () => { alive.current = false; };
  }, [account.id, authFailure]);

  async function save(path: string, body: unknown) {
    if (!current() || busy) return;
    setBusy(true); setError("");
    try {
      await portfolioRequest(path, { method: "POST", body: JSON.stringify(body) });
      if (current()) refresh();
    } catch (err) {
      if (!current()) return;
      if (err instanceof PortfolioRequestError && err.status === 401) authFailure(err);
      else setError(err instanceof Error ? err.message : "保存失败，请稍后重试。");
    } finally { if (current()) setBusy(false); }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!data) return;
    const content = JSON.stringify({ ...form, day_order: Number(form.day_order) });
    if (request.current?.content !== content) request.current = { content, id: crypto.randomUUID() };
    void save(`/accounts/${account.id}/entries`, { ...JSON.parse(content),
      expected_version: data.account_version, request_id: request.current.id });
  }

  function edit(entry: Entry, reverse: boolean) {
    setForm({ code: entry.code, kind: reverse ? "reversal" : entry.kind,
      event_date: entry.event_date, day_order: String(entry.day_order),
      quantity: reverse ? "0" : entry.quantity, price: reverse ? "0" : entry.price,
      fees: reverse ? "0" : entry.fees, total_cost: reverse ? "0" : entry.total_cost,
      history_status: entry.history_status, note: "", evidence: reverse ? "" : entry.evidence,
      reverses_id: entry.id });
    document.getElementById("ledger-entry-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const disabled = busy || account.is_archived;
  const balance = ["opening", "adjustment"].includes(form.kind);
  const reversal = form.kind === "reversal";
  return <section className="card space-y-5 p-5 sm:p-6">
    <h2 className="font-serif text-xl">持仓与交易</h2>
    <p className="text-sm leading-6 text-muted">按移动加权平均计算。买入费用计入成本，卖出费用扣减交易盈亏；现金股息不冲减成本。这里不连接券商，不代表券商核实结果。</p>
    {error ? <p role="alert" className="text-sm text-loss">{error} 如提示版本变化，请点击页面“刷新”。</p> : null}
    {!data ? <p className="text-sm text-muted">正在读取持仓与流水…</p> : <>
      {data.consent_required ? <div className="space-y-3 border border-line p-4">
        <h3 className="font-medium">首次录入前，请确认新增数据范围</h3>
        {policy ? <>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-6">{policy.policy.sections.map((text, i) => <li key={i}>{text}</li>)}</ul>
          <a className="text-sm text-jade-deep underline" href={policy.policy.privacy_path} target="_blank" rel="noreferrer">完整隐私政策</a>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={accepted} disabled={busy} onChange={(e) => setAccepted(e.target.checked)} />我已阅读，自愿保存持仓与交易数据及确认记录。</label>
          <button type="button" className={button} disabled={!accepted || busy} onClick={() => void save(`/accounts/${account.id}/consent`, { expected_version: data.account_version, consent: { accepted: true, version: policy.policy.version, sha256: policy.sha256 } })}>确认并启用交易录入</button>
        </> : <p>数据说明暂不可用，请刷新后再确认；已有数据仍可查看和导出。</p>}
      </div> : null}
      <div className="space-y-3">
        <h3 className="font-medium">当前持仓与交易盈亏</h3>
        {!data.positions.length ? <p className="text-sm text-muted">尚无有效持仓流水。可先录入有生效日期的期初持仓。</p> : data.positions.map((p) => <article key={p.code} className="space-y-2 rounded-sm border border-line p-3 text-sm">
          <h4 className="font-medium">{p.code}</h4>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[["数量（股）", p.quantity], ["持仓总成本（元）", p.total_cost], ["平均成本（元/股）", p.average_cost], ["已实现交易盈亏（元）", p.realized_pnl], ["累计费用（元）", p.fees]].map(([label, value]) => <div key={label}><dt className="text-xs text-muted">{label}</dt><dd className="mt-1 break-all tabular-nums">{amount(value)}</dd></div>)}
          </dl>
          <p className="text-xs leading-6 text-muted">历史起点：{p.known_since}；此前持仓未知，不倒推分红权益。{p.history_status === "incomplete" ? "区间内历史仍不完整，需补充核对。" : "仅按已录入的起点后流水计算。"}{p.has_adjustment ? "含人工调整，分红权益待核对。" : ""}</p>
        </article>)}
        <p className="text-xs text-muted">未实现盈亏、已收股息及组合收益率暂不计算，不能当作零收益。</p>
      </div>
      {account.is_archived ? <p className="text-sm text-muted">账本已归档，仍可查看与导出；恢复后可继续录入或更正。</p> : null}
      {!data.consent_required && !account.is_archived ? <form id="ledger-entry-form" className="scroll-mt-24 space-y-4 border-t border-line pt-5" onSubmit={submit}>
        <h3 className="font-medium">{form.reverses_id ? reversal ? "确认冲正撤销原流水" : "更正流水（保留原记录）" : "录入流水"}</h3>
        {form.reverses_id ? <p className="break-all text-xs text-muted">关联原记录：{form.reverses_id}。提交后重算全部后续流水；如出现历史超卖，将拒绝整笔操作。</p> : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1 text-sm"><span>股票代码</span><input aria-label="股票代码" className={input} value={form.code} maxLength={6} pattern="[0-9]{6}" required readOnly={!!form.reverses_id} disabled={disabled} autoComplete="off" placeholder="例如：600036" onChange={(e) => setForm({ ...form, code: e.target.value })} /></label>
          <label className="space-y-1 text-sm"><span>流水类型</span><select aria-label="流水类型" className={input} value={form.kind} disabled={disabled || !!form.reverses_id} onChange={(e) => setForm({ ...form, kind: e.target.value, price: "0", fees: "0", total_cost: ["opening", "adjustment"].includes(e.target.value) ? "" : "0" })}>{Object.entries(labels).filter(([key]) => key !== "reversal" || reversal).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
          <label className="space-y-1 text-sm"><span>生效 / 成交日期</span><input aria-label="生效日期" className={input} type="date" value={form.event_date} max={today()} required disabled={disabled || reversal} onChange={(e) => setForm({ ...form, event_date: e.target.value })} /></label>
          <label className="space-y-1 text-sm"><span>同日顺序（小的先发生）</span><input aria-label="同日顺序" className={input} type="number" min={1} max={1000000} step={1} value={form.day_order} required disabled={disabled || reversal} onChange={(e) => setForm({ ...form, day_order: e.target.value })} /></label>
          {!reversal ? <>
            <label className="space-y-1 text-sm"><span>{form.kind === "adjustment" ? "调整后总数量（股）" : "数量（股）"}</span><input aria-label="数量" className={input} inputMode="decimal" value={form.quantity} required disabled={disabled} autoComplete="off" onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></label>
            {balance ? <label className="space-y-1 text-sm"><span>{form.kind === "adjustment" ? "调整后持仓总成本（元）" : "期初总成本（元）"}</span><input aria-label="总成本" className={input} inputMode="decimal" value={form.total_cost} required disabled={disabled} autoComplete="off" onChange={(e) => setForm({ ...form, total_cost: e.target.value })} /></label> : <>
              <label className="space-y-1 text-sm"><span>成交价（元/股）</span><input aria-label="成交价" className={input} inputMode="decimal" value={form.price} required disabled={disabled} autoComplete="off" onChange={(e) => setForm({ ...form, price: e.target.value })} /></label>
              <label className="space-y-1 text-sm"><span>本笔全部费用（元）</span><input aria-label="费用" className={input} inputMode="decimal" value={form.fees} required disabled={disabled} autoComplete="off" onChange={(e) => setForm({ ...form, fees: e.target.value })} /></label>
            </>}
            <label className="space-y-1 text-sm"><span>历史完整性</span><select aria-label="历史完整性" className={input} value={form.history_status} disabled={disabled} onChange={(e) => setForm({ ...form, history_status: e.target.value })}><option value="since_date">仅确认录入起点后的历史</option><option value="incomplete">仍有缺失，待核对</option></select></label>
          </> : null}
        </div>
        <label className="block space-y-1 text-sm"><span>备注 / 原因{form.reverses_id || form.kind === "adjustment" ? "（必填）" : ""}</span><textarea aria-label="备注" className={input} maxLength={500} value={form.note} required={!!form.reverses_id || form.kind === "adjustment"} disabled={disabled} autoComplete="off" onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
        {form.kind === "adjustment" || (form.reverses_id && !reversal) ? <label className="block space-y-1 text-sm"><span>核对依据（请勿填写账户号码或密码）</span><textarea aria-label="核对依据" className={input} value={form.evidence} maxLength={500} required={form.kind === "adjustment"} disabled={disabled} autoComplete="off" onChange={(e) => setForm({ ...form, evidence: e.target.value })} /></label> : null}
        <p className="text-xs leading-6 text-muted">调整填写调整后的总数量与总成本，不是差额；不计为买卖盈亏。金额最多6位小数。历史补录、更正和冲正均保留分红待核对范围，不自动确认到账。</p>
        <div className="flex flex-wrap gap-3"><button type="submit" className={`${button} bg-ink text-paper`} disabled={disabled}>{busy ? "正在保存…" : reversal ? "确认冲正并重算" : "保存并重算"}</button>{form.reverses_id ? <button type="button" className={button} disabled={busy} onClick={() => setForm(empty())}>取消更正</button> : null}</div>
      </form> : null}
      <div className="space-y-3 border-t border-line pt-4"><h3 className="font-medium">全部流水（含更正历史）</h3>
        {!data.entries.length ? <p className="text-sm text-muted">尚无记录。</p> : data.entries.map((e) => <article key={e.id} className="space-y-2 border-b border-line pb-3 text-sm">
          <p className="flex flex-wrap gap-x-3 gap-y-1"><strong>{e.code} · {labels[e.kind]}</strong><span>{e.event_date} · 顺序 {e.day_order}</span><span className="text-muted">{e.active ? "有效" : e.kind === "reversal" ? "冲正凭据" : "已被冲正 / 更正"}</span></p>
          {e.kind !== "reversal" ? <p className="break-words text-xs text-muted">数量 {amount(e.quantity)} · 成交价 {amount(e.price)} · 费用 {amount(e.fees)}{["opening", "adjustment"].includes(e.kind) ? ` · 总成本 ${amount(e.total_cost)}` : ""}</p> : null}
          {e.note ? <p className="break-all">原因 / 备注：{e.note}</p> : null}{e.evidence ? <p className="break-all text-xs text-muted">依据：{e.evidence}</p> : null}
          {e.reverses_id ? <p className="break-all text-xs text-muted">关联原记录：{e.reverses_id}</p> : null}
          {e.active && !data.consent_required && !account.is_archived ? <div className="flex gap-3"><button type="button" className={button} disabled={busy} onClick={() => edit(e, false)}>更正</button><button type="button" className={button} disabled={busy} onClick={() => edit(e, true)}>冲正撤销</button></div> : null}
        </article>)}
      </div>
      {data.review_ranges.length ? <p className="text-xs leading-6 text-muted">已记录 {data.review_ranges.length} 次持仓变动的分红待核对范围。分红权益与到账模块尚未开放，当前没有自动应收或实收记录。</p> : null}
    </>}
  </section>;
}
