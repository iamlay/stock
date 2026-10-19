"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { login, sendSms } from "@/lib/auth";

export function LoginForm() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSend() {
    if (!/^1[3-9]\d{9}$/.test(phone)) {
      setError("请输入 11 位手机号");
      return;
    }
    setError(null);
    setSending(true);
    try {
      const result = await sendSms(phone);
      if (result.dev_code) {
        setDevCode(result.dev_code);
        setCode(result.dev_code);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证码发送失败");
    } finally {
      setSending(false);
    }
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(phone, code);
      router.push("/account");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mt-8 space-y-5">
      <div>
        <label htmlFor="phone" className="text-xs font-medium text-ink">
          手机号
        </label>
        <input
          id="phone"
          type="tel"
          inputMode="numeric"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          placeholder="请输入 11 位手机号"
          className="mt-2 w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted/70 focus:border-jade"
        />
      </div>
      <div>
        <label htmlFor="code" className="text-xs font-medium text-ink">
          验证码
        </label>
        <div className="mt-2 flex gap-2">
          <input
            id="code"
            inputMode="numeric"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="6 位验证码"
            className="w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted/70 focus:border-jade"
          />
          <button
            type="button"
            onClick={onSend}
            disabled={sending}
            className="shrink-0 rounded-sm border border-line bg-surface px-3 text-xs text-ink-soft hover:border-ink disabled:opacity-50"
          >
            {sending ? "发送中…" : "获取验证码"}
          </button>
        </div>
        {devCode ? (
          <p className="mt-2 text-xs text-jade-deep">开发模式验证码：{devCode}</p>
        ) : null}
      </div>

      {error ? <p className="text-xs text-loss">{error}</p> : null}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-sm bg-ink px-4 py-3 text-sm font-medium text-paper hover:bg-jade-deep disabled:opacity-60"
      >
        {submitting ? "登录中…" : "登录"}
      </button>

      <p className="text-xs leading-6 text-muted">
        本项目不提供微信登录。开发模式下验证码直接返回；生产环境接入短信服务商后关闭该开关。
      </p>
    </form>
  );
}
