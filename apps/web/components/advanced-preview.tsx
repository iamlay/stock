"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchAdvancedSample, fetchPersonalPreview, selectPersonalPreview,
  type AdvancedPreviewData, type PersonalPreviewState,
} from "@/lib/auth";

export type PreviewFeature = "grid" | "bollinger" | "financial";

function PreviewCard({ data, feature }: { data: AdvancedPreviewData; feature: PreviewFeature }) {
  const card = data.cards.find((item) => item.feature === feature);
  if (!card) return null;
  return <article className="rounded-sm border border-line bg-surface p-5 text-left">
    <p className="text-xs font-medium text-jade-deep">
      {data.kind === "sample" ? "固定教学样例 · 非真实行情" : "我的单标的预览 · 真实数据"}
    </p>
    <h3 className="mt-2 text-lg font-medium text-ink">{data.name} · {card.title}</h3>
    <p className="mt-1 text-xs text-muted">{data.code} · 数据日期：{card.as_of ?? "暂无日期"}</p>
    <p className="mt-3 text-sm leading-6 text-ink-soft">{card.purpose}</p>
    {Object.keys(card.metrics).length ? <dl className="mt-4 grid gap-3 sm:grid-cols-2">
      {Object.entries(card.metrics).map(([label, value]) => <div key={label} className="rounded-sm bg-paper p-3">
        <dt className="text-xs text-muted">{label}</dt>
        <dd className="mt-1 font-medium text-ink">{value}</dd>
      </div>)}
    </dl> : <p className="mt-4 text-sm text-muted">该标的此项数据不足，暂不能展示；不会用教学样例替代真实数据。</p>}
    <p className="mt-4 text-xs leading-5 text-muted">{card.scope}</p>
  </article>;
}

export function AdvancedPreview({ feature, authenticated }: { feature: PreviewFeature; authenticated: boolean }) {
  const [sample, setSample] = useState<AdvancedPreviewData | null>(null);
  const [personal, setPersonal] = useState<PersonalPreviewState | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setSample(null);
    setPersonal(null);
    setCode("");
    Promise.allSettled([
      fetchAdvancedSample(),
      authenticated ? fetchPersonalPreview() : Promise.resolve(null),
    ]).then(([example, account]) => {
      if (!active) return;
      if (example.status === "fulfilled") setSample(example.value);
      if (account.status === "fulfilled") {
        setPersonal(account.value);
        setCode(account.value?.choices[0]?.code ?? "");
      }
      if (example.status === "rejected" || account.status === "rejected") {
        setError("部分预览暂时无法加载，请重试。");
      }
      setLoading(false);
    });
    return () => { active = false; };
  }, [authenticated, attempt]);

  async function select() {
    if (!code || busy) return;
    setBusy(true);
    setError("");
    try {
      setPersonal(await selectPersonalPreview(code));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "预览失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  return <div className="mx-auto mb-6 max-w-2xl space-y-4">
    {loading ? <p role="status" className="text-sm text-muted">正在加载功能预览…</p> : null}
    {sample ? <PreviewCard data={sample} feature={feature} /> : null}
    {personal?.enabled ? <section className="space-y-3 text-left">
      {personal.preview ? <PreviewCard data={personal.preview} feature={feature} /> : null}
      {personal.message ? <p className="text-sm text-muted">{personal.message}</p> : null}
      {!personal.selected_code ? <div className="rounded-sm border border-line p-4">
        <h3 className="font-medium text-ink">体验一个自己的自选股票</h3>
        <p className="mt-2 text-sm leading-6 text-muted">每个账号只能选择一次，网格、布林、财务共用同一标的；删除自选不会重置名额。此预览不会启动 7 天试用。</p>
        {personal.choices.length ? <form className="mt-3 flex flex-wrap gap-3" onSubmit={(event) => { event.preventDefault(); void select(); }}>
          <label className="flex items-center gap-2 text-sm">自选股票
            <select value={code} disabled={busy} onChange={(event) => setCode(event.target.value)} className="max-w-full rounded-sm border border-line bg-paper p-2">
              {personal.choices.map((choice) => <option value={choice.code} key={choice.code}>{choice.name} {choice.code}</option>)}
            </select>
          </label>
          <button disabled={busy || !code} className="rounded-sm bg-ink px-4 py-2 text-sm text-paper disabled:opacity-50">
            {busy ? "正在绑定…" : "绑定并查看预览"}
          </button>
        </form> : <Link className="mt-3 inline-block text-sm text-jade-deep underline" href="/stocks">先添加一个股票自选</Link>}
      </div> : null}
    </section> : null}
    {error ? <div role="alert" className="text-sm text-red-700">{error} <button disabled={busy || loading} className="underline" onClick={() => setAttempt((value) => value + 1)}>重新加载</button></div> : null}
  </div>;
}
