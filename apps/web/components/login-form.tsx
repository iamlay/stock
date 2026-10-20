"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { emailLogin, login, registerEmail, sendSms } from "@/lib/auth";

type Mode = "email" | "phone";

export function LoginForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("email");
  const [registering, setRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
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

    if (mode === "email") {
      if (registering && password !== confirm) {
        setError("两次输入的密码不一致");
        return;
      }
      setSubmitting(true);
      try {
        if (registering) {
          const result = await registerEmail(email, password);
          if (result.devVerificationToken) {
            router.push(
              `/verify-email?token=${encodeURIComponent(result.devVerificationToken)}`,
            );
          } else {
            router.push("/account");
          }
          router.refresh();
        } else {
          await emailLogin(email, password);
          router.push("/account");
          router.refresh();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "登录失败");
      } finally {
        setSubmitting(false);
      }
      return;
    }

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
    <div className="mt-8">
      <div className="flex gap-5 border-b border-line text-sm">
        <button
          type="button"
          onClick={() => {
            setMode("email");
            setError(null);
          }}
          className={`-mb-px border-b-2 px-1 pb-2 ${
            mode === "email"
              ? "border-ink font-medium text-ink"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          邮箱登录
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("phone");
            setError(null);
          }}
          className={`-mb-px border-b-2 px-1 pb-2 ${
            mode === "phone"
              ? "border-ink font-medium text-ink"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          手机号登录
        </button>
      </div>

      <form onSubmit={onSubmit} className="mt-6 space-y-5">
        {mode === "email" ? (
          <>
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
            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="text-xs font-medium text-ink">
                  密码
                </label>
                {!registering ? (
                  <Link
                    href="/forgot-password"
                    className="text-xs text-jade-deep hover:underline"
                  >
                    忘记密码？
                  </Link>
                ) : null}
              </div>
              <input
                id="password"
                type="password"
                autoComplete={registering ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="至少 8 位"
                className="mt-2 w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted/70 focus:border-jade"
              />
            </div>
            {registering ? (
              <div>
                <label htmlFor="confirm" className="text-xs font-medium text-ink">
                  确认密码
                </label>
                <input
                  id="confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  placeholder="再输入一次"
                  className="mt-2 w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted/70 focus:border-jade"
                />
              </div>
            ) : null}
            <p className="text-xs leading-6 text-muted">
              {registering
                ? "注册后会发送验证邮件，验证后账号更安全；会员仍通过兑换码开通。"
                : "使用邮箱和密码登录。忘记密码可通过邮箱重置。"}
            </p>
          </>
        ) : (
          <>
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
              <p className="mt-2 text-xs leading-6 text-muted">
                手机号登录保留，接入短信服务商前生产环境不可用；日常请使用邮箱登录。
              </p>
            </div>
          </>
        )}

        {error ? <p className="text-xs text-loss">{error}</p> : null}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-sm bg-ink px-4 py-3 text-sm font-medium text-paper hover:bg-jade-deep disabled:opacity-60"
        >
          {submitting
            ? mode === "email" && registering
              ? "注册中…"
              : "登录中…"
            : mode === "email" && registering
              ? "注册并登录"
              : "登录"}
        </button>

        {mode === "email" ? (
          <button
            type="button"
            onClick={() => {
              setRegistering((value) => !value);
              setError(null);
            }}
            className="w-full text-center text-xs text-jade-deep hover:underline"
          >
            {registering ? "已有账号？返回登录" : "还没有账号？用邮箱注册"}
          </button>
        ) : null}
      </form>
    </div>
  );
}
