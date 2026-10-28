"use client";

import { PortfolioLedger } from "@/components/portfolio-ledger";
import { flushSync } from "react-dom";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  portfolioRequest, PortfolioRequestError, validPortfolioPolicy,
  type PortfolioPolicy, type PortfolioAccount, type PortfolioList,
} from "@/lib/portfolio";
import { getToken } from "@/lib/auth";

const button = "rounded-sm border border-line px-4 py-2 text-sm disabled:opacity-50 hover:border-jade";
const input = "w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-jade";

function analyticsPresent(): boolean {
  const globals = window as unknown as { _hmt?: unknown; va?: unknown };
  return Boolean(globals._hmt || globals.va || document.querySelector(
    'script[src*="hm.baidu.com"],script[src*="/insights/"],script[src*="vercel-insights"]',
  ));
}

export function PortfolioPanel() {
  const [policy, setPolicy] = useState<PortfolioPolicy | null>(null);
  const [list, setList] = useState<PortfolioList | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [authRequired, setAuthRequired] = useState(false);
  const generation = useRef(0);
  const operation = useRef(0);
  const sessionToken = useRef<string | null>(null);
  const account = list?.items[0] ?? null;

  const fail = useCallback((err: unknown) => {
    setError(err instanceof Error ? err.message : "操作失败，请稍后重试。");
    if (err instanceof PortfolioRequestError && err.status === 401) {
      generation.current += 1;
      setList(null); setName(""); setPolicy(null); setAccepted(false);
      setConfirmDelete(""); setDeleting(false); setAuthRequired(true);
    }
  }, []);

  const load = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true); setError(""); setAuthRequired(false);
    setList(null); setName("");
    const token = getToken();
    if (!token) { setAuthRequired(true); setLoading(false); return; }
    try {
      const [policyResult, accountResult] = await Promise.allSettled([
        portfolioRequest<unknown>("/policy"), portfolioRequest<PortfolioList>("/accounts"),
      ]);
      if (current !== generation.current) return;
      if (token !== getToken()) { window.location.replace("/portfolio"); return; }
      if (accountResult.status === "rejected") throw accountResult.reason;
      const accounts = accountResult.value;
      setList(accounts); setName(accounts.items[0]?.name ?? ""); sessionToken.current = token;
      if (policyResult.status === "fulfilled" && validPortfolioPolicy(policyResult.value)) {
        setPolicy(policyResult.value);
      } else {
        setPolicy(null); setError("数据说明暂不可用，暂不能创建账本；已有账本仍可管理和导出。");
      }
      setAccepted(false); setDeleting(false); setConfirmDelete("");
    } catch (err) { if (current === generation.current) fail(err); }
    finally { if (current === generation.current) setLoading(false); }
  }, [fail]);

  useEffect(() => {
    // Entering through a public SPA page may leave analytics globals alive after unmount.
    // Reload BEFORE fetching or displaying ANY private metadata.
    if (analyticsPresent()) { window.location.replace("/portfolio"); return; }
    if (!getToken()) { setAuthRequired(true); setLoading(false); return; }
    void load();
    return () => { generation.current += 1; };
  }, [load]);

  useEffect(() => {
    const revoke = () => {
      generation.current += 1; operation.current += 1; setBusy(false);
      setList(null); setPolicy(null); setName(""); setAccepted(false);
      setConfirmDelete(""); setDeleting(false); setMessage("");
      if (getToken()) void load();
      else { setLoading(false); setAuthRequired(true); }
    };
    const storage = (event: StorageEvent) => { if (event.key === "stocklab.token" || event.key === null) revoke(); };
    const pagehide = () => {
      generation.current += 1; operation.current += 1;
      flushSync(() => {
        setList(null); setPolicy(null); setName(""); setAccepted(false); setBusy(false);
        setConfirmDelete(""); setDeleting(false); setMessage(""); setError(""); setLoading(true);
      });
    };
    window.addEventListener("pagehide", pagehide);
    window.addEventListener("storage", storage);
    window.addEventListener("pageshow", revoke);
    return () => { window.removeEventListener("pagehide", pagehide); window.removeEventListener("storage", storage); window.removeEventListener("pageshow", revoke); };
  }, [load]);

  function confirmDraftExit() {
    return !document.querySelector("[data-portfolio-draft]") || window.confirm("当前录入尚未保存，此操作会清空表单，是否继续？");
  }

  async function mutate(action: () => Promise<unknown>, success: string) {
    if (sessionToken.current !== getToken()) { window.location.replace("/portfolio"); return; }
    if (!confirmDraftExit()) return;
    const current = generation.current;
    const op = ++operation.current;
    setBusy(true); setError(""); setMessage("");
    try {
      await action();
      if (current !== generation.current || sessionToken.current !== getToken()) return;
      await load();
      if (op === operation.current && sessionToken.current === getToken()) setMessage(success);
    } catch (err) {
      if (current !== generation.current) return;
      fail(err);
      if (err instanceof PortfolioRequestError && ["privacy_policy_changed", "account_changed"].includes(err.code)) {
        setAccepted(false); setDeleting(false); setConfirmDelete("");
        setError(`${err.message} 请点击“刷新”后重新操作。`);
      }
    } finally { if (op === operation.current) setBusy(false); }
  }

  function create(event: FormEvent) {
    event.preventDefault();
    if (!policy || !accepted || !name.trim() || busy) return;
    void mutate(() => portfolioRequest("/accounts", { method: "POST", body: JSON.stringify({
      name: name.trim(), currency: "CNY", consent: {
        accepted: true, version: policy.policy.version, sha256: policy.sha256,
      },
    }) }), "私人账本已建立，可以录入期初持仓和买卖流水。");
  }

  function update(patch: { name?: string; is_archived?: boolean }) {
    if (!account || busy) return;
    void mutate(() => portfolioRequest(`/accounts/${account.id}`, { method: "PATCH", body: JSON.stringify({
      expected_version: account.version, ...patch,
    }) }), "账本信息已更新。");
  }

  async function download() {
    if (sessionToken.current !== getToken()) { window.location.replace("/portfolio"); return; }
    setBusy(true); setError("");
    const current = generation.current;
    const op = ++operation.current;
    try {
      const data = await portfolioRequest<unknown>("/export");
      if (current !== generation.current || sessionToken.current !== getToken()) return;
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = "stocklab-portfolio.json";
      link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage("已导出账户、持仓流水、冲正历史及确认记录。");
    } catch (err) { if (current === generation.current) fail(err); }
    finally { if (op === operation.current) setBusy(false); }
  }

  if (authRequired) return <section className="card space-y-3 p-6">
    <h1 className="font-serif text-2xl">私人账本</h1><p>请登录并验证邮箱后管理自己的账本。</p>
    <a className="inline-block text-jade-deep underline" href="/login?next=%2Fportfolio">登录后继续</a>
  </section>;

  return <div className="mx-auto max-w-5xl space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="text-xs tracking-widest text-jade-deep">PRIVATE PORTFOLIO</p>
        <h1 className="mt-2 font-serif text-3xl">私人账本</h1>
        <p className="mt-2 text-sm leading-6 text-muted">录入已有持仓或记录买卖，明确成本口径，查看分红参考。实际收息核对将逐步开放。</p>
      </div><a href="/account" className="text-sm text-jade-deep hover:underline">返回个人中心</a>
    </header>
    {loading ? <p role="status" className="py-8 text-sm text-muted">正在读取私人账本…</p> : null}
    {error ? <p role="alert" className="rounded-sm border border-loss/30 p-3 text-sm text-loss">{error}</p> : null}
    {message ? <p role="status" className="text-sm text-jade-deep">{message}</p> : null}
    {!loading ? <button type="button" className={button} disabled={busy} onClick={() => { if (confirmDraftExit()) void load(); }}>刷新</button> : null}
    {!loading && list && !account ? <section className="card space-y-4 p-5 sm:p-6">
      {!list.create_enabled ? <p className="text-sm text-muted">私人账本正在内测，暂未开放创建。已有账本仍可查看、维护、导出和删除。</p> : policy ? <>
        <h2 className="font-medium">{policy.policy.title}</h2>
        <p className="break-all text-xs text-muted">版本：{policy.policy.version}</p>
        <ul className="list-disc space-y-2 pl-5 text-sm leading-7 text-ink-soft">
          {policy.policy.sections.map((section, i) => <li key={i}>{section}</li>)}
        </ul>
        <a href={policy.policy.privacy_path} target="_blank" rel="noreferrer" className="text-sm text-jade-deep underline">查看完整隐私政策</a>
        <form onSubmit={create} className="space-y-4">
          <label className="flex items-start gap-2 text-sm leading-6">
            <input type="checkbox" checked={accepted} onChange={(event) => { setAccepted(event.target.checked); if (!event.target.checked) setName(""); }} className="mt-1" disabled={busy} />
            我已阅读以上数据说明，自愿建立私人账本并保存确认记录。
          </label>
          {accepted ? <label className="block space-y-2 text-sm"><span>账本名称</span>
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={40} required autoComplete="off" placeholder="例如：长期收息" className={input} disabled={busy} />
          </label> : null}
          <p className="text-xs text-muted">人民币 · 一个免费账本；归档不会释放账户数量，不需要填写真实证券账户号码。</p>
          <button disabled={!accepted || !name.trim() || busy} className={`${button} bg-ink text-paper`} type="submit">{busy ? "正在保存…" : "创建私人账本"}</button>
        </form>
      </> : null}
    </section> : null}
    {!loading && account ? <PortfolioLedger key={`${account.id}:${account.version}`} account={account} policy={policy} refresh={(message) => { if (message) setMessage(message); void load(); }} authFailure={fail} /> : null}
    {!loading && account ? <details className="card space-y-5 p-5 sm:p-6"><summary className="cursor-pointer text-sm">账本设置 · 名称、导出、归档与删除</summary>
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="break-all font-medium">{account.name}</h2>
        <span className="text-xs text-muted">{account.is_archived ? "已归档" : "使用中"} · 人民币</span></div>
      <form onSubmit={(event) => { event.preventDefault(); update({ name: name.trim() }); }} className="space-y-3">
        <label className="block space-y-2 text-sm"><span>修改账本名称</span>
          <input value={name} onChange={(event) => setName(event.target.value)} maxLength={40} autoComplete="off" required className={input} disabled={busy} />
        </label><button type="submit" className={button} disabled={!name.trim() || busy || name.trim() === account.name}>保存名称</button>
      </form>
      <div className="flex flex-wrap gap-3">
        <button type="button" className={button} disabled={busy} onClick={() => update({ is_archived: !account.is_archived })}>{account.is_archived ? "恢复账本" : "归档账本"}</button>
        <button type="button" className={button} disabled={busy} onClick={() => void download()}>免费导出 JSON</button>
        <button type="button" className={`${button} text-loss`} disabled={busy} onClick={() => { setDeleting(!deleting); setConfirmDelete(""); }}>删除账本</button>
      </div>
      <p className="text-xs leading-6 text-muted">基础管理不依赖会员。归档保留全部信息；删除会移除在线账户、持仓交易及操作记录，最小确认和删除凭据仍会保留。备份中的历史数据需按恢复清理流程处理。</p>
      {deleting ? <form className="space-y-3 border-t border-line pt-4" onSubmit={(event) => {
        event.preventDefault();
        if (confirmDelete !== "删除账本" || busy) return;
        void mutate(() => portfolioRequest(`/accounts/${account.id}`, { method: "DELETE", body: JSON.stringify({
          expected_version: account.version, confirmation: "DELETE",
        }) }), "在线账本已删除，最小确认和删除凭据已保留。");
      }}>
        <label className="block space-y-2 text-sm"><span>请输入“删除账本”确认</span>
          <input value={confirmDelete} onChange={(event) => setConfirmDelete(event.target.value)} autoComplete="off" className={input} disabled={busy} /></label>
        <button type="submit" className={`${button} text-loss`} disabled={confirmDelete !== "删除账本" || busy}>确认删除</button>
        <button type="button" className="ml-3 text-sm text-muted" onClick={() => { setDeleting(false); setConfirmDelete(""); }} disabled={busy}>取消</button>
      </form> : null}
    </details> : null}

  </div>;
}
