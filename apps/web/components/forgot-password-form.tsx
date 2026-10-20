"use client";

import Link from "next/link";
import { useState } from "react";

import { forgotPassword } from "@/lib/auth";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await forgotPassword(email);
      setSent(true);
      setDevToken(result.dev_reset_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="card mx-auto mt-8 max-w-md p-6">
        <h1 className="font-serif text-2xl text-ink">邮件已发送</h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          如果该邮箱已注册，你会收到一封重置密码邮件，链接 30 分钟内有效。
        </p>
        {devToken ? (
          <Link
            href={`/reset-password?token=${encodeURIComponent(devToken)}`}
            className="mt-4 inline-block break-all text-xs text-jade-deep hover:underline"
          >
            开发模式：打开重置链接
          </Link>
        ) : null}
        <div className="mt-6">
          <Link href="/login" className="text-sm text-jade-deep hover:underline">
            返回登录
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="card mx-auto mt-8 max-w-md p-6">
      <h1 className="font-serif text-2xl text-ink">忘记密码</h1>
      <p className="mt-2 text-sm text-muted">输入注册邮箱，我们会发送重置链接。</p>
      <form onSubmit={onSubmit} className="mt-5 space-y-4">
        <div>
          <label htmlFor="email" className="text-xs font-medium text-ink">
            邮箱
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            className="mt-2 w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted/70 focus:border-jade"
          />
        </div>
        {error ? <p className="text-xs text-loss">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-sm bg-ink px-4 py-2.5 text-sm text-paper hover:bg-jade-deep disabled:opacity-60"
        >
          {busy ? "发送中…" : "发送重置邮件"}
        </button>
      </form>
      <Link href="/login" className="mt-4 inline-block text-xs text-muted hover:text-ink">
        返回登录
      </Link>
    </div>
  );
}
