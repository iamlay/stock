"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Quota } from "@/lib/api";
import { ApiError, fetchBacktestQuota, fetchMe, startTrial, type Me } from "@/lib/auth";
import { trialExpiry, trialState } from "@/lib/trial";

export function TrialPanel({ profile, onProfile }: { profile: Me; onProfile: (me: Me) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loginRequired, setLoginRequired] = useState(false);
  const [now, setNow] = useState(Date.now);
  const [quota, setQuota] = useState<Quota | null>(null);
  const inFlight = useRef(false);
  const refreshVersion = useRef(0);
  const state = trialState(profile, now);
  const rights = profile.entitlements;

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    const version = ++refreshVersion.current;
    try {
      const current = await fetchMe();
      if (version !== refreshVersion.current) return;
      onProfile(current);
      setNow(Date.now());
      setError(null);
      setLoginRequired(false);
    } catch (err) {
      if (version !== refreshVersion.current) return;
      setError(err instanceof Error ? err.message : "权益刷新失败，请稍后重试。");
      setLoginRequired(err instanceof ApiError && err.status === 401);
    }
  }, [onProfile]);

  useEffect(() => {
    let live = true;
    setQuota(null);
    fetchBacktestQuota().then((value) => { if (live) setQuota(value); }).catch(() => undefined);
    return () => { live = false; };
  }, [profile]);

  useEffect(() => {
    // Reconcile an upgrade in another tab and an expiry while this page stays open.
    const focus = () => { void refresh(); };
    window.addEventListener("focus", focus);
    const expires = Date.parse(rights?.expires_at ?? "");
    const remaining = expires - Date.now();
    const timer = state === "active" && remaining > 0 ? window.setTimeout(() => {
      setNow(Date.now());
      setSuccess(false);
      // Conservatively hide expired capabilities even if the refresh is offline.
      onProfile({ ...profile, entitlements: { ...rights, state: "free", trial_used: true,
        trial_eligible: false, capabilities: { advanced_data: false, history: false,
          advanced_alerts: false, unlimited_backtests: false, unlimited_watchlist: false } } });
      void refresh();
    }, Math.min(remaining + 100, 2_147_483_647)) : undefined;
    return () => {
      window.removeEventListener("focus", focus);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [refresh, rights, state, profile, onProfile]);

  async function claim() {
    if (inFlight.current || state !== "eligible") return;
    inFlight.current = true;
    refreshVersion.current += 1;
    setBusy(true);
    setError(null);
    setSuccess(false);
    try {
      const current = await startTrial(profile.id);
      onProfile(current);
      setNow(Date.now());
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "领取失败，请稍后重试。");
      setLoginRequired(err instanceof ApiError && err.status === 401);
      // A conflicting claim/upgrade can change eligibility. Do not treat this as success.
      if (err instanceof ApiError && err.status === 403) {
        try { onProfile(await fetchMe()); } catch { /* Keep the original rejection visible. */ }
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  const title = state === "active" ? "会员体验进行中"
    : state === "member" ? "你已拥有会员权益"
    : state === "expired" || state === "used" ? "体验已结束或已使用"
    : "体验高级研究功能";

  return <section id="trial" aria-labelledby="trial-title" className="card scroll-mt-6 p-5 sm:p-6">
    <h2 id="trial-title" className="text-lg font-medium text-ink">{title}</h2>
    {state === "eligible" ? <>
      <p className="mt-2 text-sm leading-6 text-ink-soft">
        每个账号可领取一次 7 天体验。点击后立即开始连续 7×24 小时计时；不需要付款，不会自动扣费。
      </p>
      <p className="mt-2 text-sm leading-6 text-muted">
        可使用高级数据、回测历史、高级提醒和不限数量自选。回测计算仍使用免费账号额度，不会因领取重置当日用量。
      </p>
    </> : null}
    {state === "active" ? <>
      <p className="mt-2 text-sm text-ink-soft">到期时间：{trialExpiry(rights.expires_at)}</p>
      <p className="mt-2 text-sm leading-6 text-muted">
        已开放高级数据、回测历史、高级提醒和不限数量自选。到期后保留数据与设置，高级提醒暂停，基础提醒继续；不会自动扣费。
      </p>
    </> : null}
    {state === "member" ? <p className="mt-2 text-sm leading-6 text-muted">
      无需领取体验，现有会员有效期不会被试用覆盖。
      {rights.expires_at ? `有效期至 ${trialExpiry(rights.expires_at)}。` : "当前为长期会员。"}
    </p> : null}
    {state === "used" || state === "expired" ? <p className="mt-2 text-sm leading-6 text-muted">
      每个账号仅可体验一次，不能重复领取。已保存的数据和提醒配置仍保留；开通会员后可恢复高级功能。
    </p> : null}
    {state === "unverified" ? <p className="mt-2 text-sm leading-6 text-muted">
      领取体验需要当前账号拥有已验证邮箱。请先完成邮箱验证；仅手机号账号暂不支持领取。验证本身不会启动体验。
    </p> : null}
    {state === "unavailable" ? <p className="mt-2 text-sm text-muted">
      暂无法确认体验资格，请刷新权益状态或稍后再试。
    </p> : null}

    <p className="mt-3 text-sm text-ink-soft" aria-live="polite">
      {quota ? (quota.limit === null ? "当前回测计算不限次数。"
        : `回测额度：每天 ${quota.limit} 次，今日已用 ${quota.used} 次，剩余 ${quota.remaining} 次（UTC 零点重置）。`)
        : rights?.daily_backtest_limit != null
          ? `回测额度：每天 ${rights.daily_backtest_limit} 次；今日剩余额度暂未获取。`
          : "回测额度暂未获取，请稍后刷新。"}
    </p>

    <div className="mt-4 flex flex-wrap gap-3">
      {state === "eligible" && !loginRequired ? <button type="button" onClick={claim} disabled={busy}
        className="rounded-sm bg-ink px-4 py-2 text-sm text-paper disabled:opacity-50">
        {busy ? "正在领取…" : "开始 7 天体验"}
      </button> : null}
      {loginRequired ? <Link href="/login?next=%2Faccount%23trial" className="text-sm text-jade-deep underline">
        重新登录后继续
      </Link> : null}
      <button type="button" onClick={() => { void refresh(); }} disabled={busy}
        className="rounded-sm border border-line px-4 py-2 text-sm text-ink-soft disabled:opacity-50">刷新权益状态</button>
      {state === "used" || state === "expired" || state === "active" ?
        <Link href="/pricing" className="rounded-sm border border-line px-4 py-2 text-sm text-jade-deep">查看会员方案</Link> : null}
    </div>
    {error ? <p role="alert" className="mt-3 text-sm text-loss">{error}</p> : null}
    {success && state === "active" ? <p role="status" className="mt-3 text-sm text-jade-deep">体验已开通，可以开始以下研究任务。</p> : null}

    {state === "active" ? <div className="mt-6 border-t border-line pt-5">
      <h3 className="text-sm font-medium text-ink">三步了解高级功能</h3>
      <ol className="mt-3 grid gap-3 md:grid-cols-3">
        {[
          ["查看一个关注标的", "从自选打开详情；还没有自选时，可先浏览列表并添加感兴趣的标的。", "/watchlist", "打开我的自选"],
          ["理解一个高级指标", "查看股息率网格，比较当前价格与目标股息率对应价格。指标用于研究，不代表收益承诺。", "/stocks/grid", "查看股息率网格"],
          ["设置一个高级提醒", "按自己的研究需要设置网格或低位共振提醒；提醒是观察信号，不是交易指令。", "/notifications", "设置研究提醒"],
        ].map(([heading, body, href, label], index) => <li key={href} className="rounded-sm border border-line p-4">
          <p className="text-sm font-medium text-ink">{index + 1}. {heading}</p>
          <p className="mt-2 text-xs leading-6 text-muted">{body}</p>
          <Link href={href} className="mt-3 inline-block text-sm text-jade-deep underline">{label} →</Link>
        </li>)}
      </ol>
    </div> : null}
  </section>;
}
