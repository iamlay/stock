"use client";

import { ContextLink } from "@/components/context-link";

import { useEffect, useState } from "react";

import { addWatchlist, fetchWatchlist, getToken, removeWatchlist } from "@/lib/auth";

export function WatchlistButton({ code }: { code: string }) {
  const [saved, setSaved] = useState(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    setLoggedIn(true);
    fetchWatchlist()
      .then((items) => setSaved(items.some((item) => item.code === code)))
      .catch(() => undefined)
      .finally(() => setReady(true));
  }, [code]);

  if (!loggedIn) {
    return (
      <ContextLink
        href="/login"
        className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft hover:border-ink"
      >
        登录后加自选
      </ContextLink>
    );
  }

  async function onToggle() {
    setBusy(true);
    setError(null);
    try {
      if (saved) {
        await removeWatchlist(code);
        setSaved(false);
      } else {
        await addWatchlist(code);
        setSaved(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onToggle}
        disabled={!ready || busy}
        className={`rounded-sm border px-3 py-1.5 text-xs disabled:opacity-50 ${
          saved
            ? "border-jade bg-jade-soft text-jade-deep"
            : "border-line bg-surface text-ink-soft hover:border-ink"
        }`}
      >
        {busy ? "处理中…" : saved ? "已加入自选" : "加入自选"}
      </button>
      {error ? <span className="text-[11px] text-loss">{error}</span> : null}
    </div>
  );
}
