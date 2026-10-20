"use client";

import Link from "next/link";
import { useState } from "react";

import { resetPassword } from "@/lib/auth";

export function ResetPasswordForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("链接缺少 token，请从邮件中重新打开。");
      return;
    }
    if (password !== confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    setBusy(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="card mx-auto mt-8 max-w-md p-6">
        <h1 className="font-serif text-2xl text-ink">密码已重置</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          旧密码和之前的登录状态都已失效，请用新密码登录。
        </p>
        <Link
          href="/login"
          className="mt-6 inline-block rounded-sm bg-ink px-4 py-2 text-sm text-paper hover:bg-jade-deep"
        >
          去登录
        </Link>
      </div>
    );
  }

  return (
    <div className="card mx-auto mt-8 max-w-md p-6">
      <h1 className="font-serif text-2xl text-ink">设置新密码</h1>
      <p className="mt-2 text-sm text-muted">至少 8 位，重置后所有设备需要重新登录。</p>
      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        <div>
          <label htmlFor="password" className="text-xs font-medium text-ink">
            新密码
          </label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-2 w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none focus:border-jade"
          />
        </div>
        <div>
          <label htmlFor="confirm" className="text-xs font-medium text-ink">
            确认新密码
          </label>
          <input
            id="confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            className="mt-2 w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none focus:border-jade"
          />
        </div>
        {error ? <p className="text-xs text-loss">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-sm bg-ink px-4 py-2.5 text-sm text-paper hover:bg-jade-deep disabled:opacity-60"
        >
          {busy ? "提交中…" : "重置密码"}
        </button>
      </form>
      <Link href="/login" className="mt-4 inline-block text-xs text-muted hover:text-ink">
        返回登录
      </Link>
    </div>
  );
}
