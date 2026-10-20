"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { verifyEmail } from "@/lib/auth";

export function VerifyEmailPanel({ token }: { token: string }) {
  const [state, setState] = useState<"loading" | "done" | "error">("loading");
  const [email, setEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setState("error");
      setError("链接缺少 token，请从邮件中重新打开。");
      return;
    }
    verifyEmail(token)
      .then((result) => {
        setEmail(result.email);
        setState("done");
      })
      .catch((err) => {
        setState("error");
        setError(err instanceof Error ? err.message : "验证失败");
      });
  }, [token]);

  return (
    <div className="card mx-auto mt-8 max-w-md p-6">
      {state === "loading" ? (
        <p className="py-8 text-center text-sm text-muted">正在验证邮箱…</p>
      ) : null}

      {state === "done" ? (
        <>
          <p className="text-xs uppercase tracking-[0.18em] text-jade-deep">Verified</p>
          <h1 className="mt-2 font-serif text-2xl text-ink">邮箱已验证</h1>
          <p className="mt-3 text-sm leading-6 text-muted">
            {email} 已完成验证，可以正常使用账号和找回密码。
          </p>
          <Link
            href="/account"
            className="mt-6 inline-block rounded-sm bg-ink px-4 py-2 text-sm text-paper hover:bg-jade-deep"
          >
            进入个人中心
          </Link>
        </>
      ) : null}

      {state === "error" ? (
        <>
          <h1 className="font-serif text-2xl text-ink">验证链接无效</h1>
          <p className="mt-3 text-sm leading-6 text-loss">{error}</p>
          <p className="mt-3 text-xs leading-6 text-muted">
            链接 24 小时内有效。登录后可以在个人中心重新发送验证邮件。
          </p>
          <Link
            href="/login"
            className="mt-6 inline-block text-sm text-jade-deep hover:underline"
          >
            返回登录
          </Link>
        </>
      ) : null}
    </div>
  );
}
