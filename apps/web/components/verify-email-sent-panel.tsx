"use client";

import Link from "next/link";
import { useState } from "react";

import { resendVerification } from "@/lib/auth";

export function VerifyEmailSentPanel({ email }: { email: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onResend() {
    if (!email) {
      setError("缺少邮箱地址，请返回登录页重新注册。");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await resendVerification(email);
      setMessage("验证邮件已重新发送，请检查收件箱和垃圾箱。");
      setDevToken(result.dev_verification_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败，请稍后再试");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card mx-auto mt-8 max-w-md p-6">
      <p className="text-xs uppercase tracking-[0.18em] text-jade-deep">Check your inbox</p>
      <h1 className="mt-2 font-serif text-2xl text-ink">验证邮件已发送</h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        我们向 {email || "你的邮箱"} 发送了一封验证邮件。点击邮件里的链接完成验证后，才能登录。
      </p>
      <p className="mt-2 text-xs leading-6 text-muted">
        没收到？检查垃圾箱，或 1 分钟后重发。
      </p>

      {message ? <p className="mt-3 text-xs text-jade-deep">{message}</p> : null}
      {error ? <p className="mt-3 text-xs text-loss">{error}</p> : null}
      {devToken ? (
        <Link
          href={`/verify-email?token=${encodeURIComponent(devToken)}`}
          className="mt-3 block text-xs text-jade-deep hover:underline"
        >
          开发模式：打开验证链接
        </Link>
      ) : null}

      <div className="mt-6 flex items-center gap-4">
        <button
          type="button"
          onClick={onResend}
          disabled={busy}
          className="rounded-sm bg-ink px-4 py-2 text-sm text-paper hover:bg-jade-deep disabled:opacity-60"
        >
          {busy ? "发送中…" : "重新发送"}
        </button>
        <Link href="/login" className="text-sm text-jade-deep hover:underline">
          返回登录
        </Link>
      </div>
    </div>
  );
}
