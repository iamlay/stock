import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/chrome";

export const metadata: Metadata = { title: "登录" };

export default function LoginPage() {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto grid max-w-6xl gap-10 px-6 py-14 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="hidden rounded-sm bg-ink p-8 text-paper lg:block">
          <p className="text-xs uppercase tracking-[0.18em] text-jade">Invite Only</p>
          <h1 className="mt-6 font-serif text-3xl leading-snug">
            内测阶段，
            <br />
            邀请码即门票。
          </h1>
          <p className="mt-4 text-sm leading-6 text-paper/70">
            当前不开放公开注册，也不接入微信登录。通过邀请码或兑换码开通后，使用手机号登录即可。
          </p>
          <ul className="mt-10 space-y-4 text-sm text-paper/80">
            {["手机号 + 验证码，无密码", "邀请码 7 天试用", "兑换码开通会员"].map((item) => (
              <li key={item} className="flex items-center gap-3 border-b border-white/10 pb-4">
                <span className="h-1.5 w-1.5 rounded-full bg-jade" />
                {item}
              </li>
            ))}
          </ul>
          <p className="mt-10 text-xs leading-6 text-paper/50">
            登录接口将在 W6 接入；本页为 Sprint 0 界面骨架。
          </p>
        </section>

        <section className="mx-auto w-full max-w-md">
          <p className="text-xs text-muted">StockLab 工作台</p>
          <h2 className="mt-2 font-serif text-3xl text-ink">登录</h2>
          <p className="mt-2 text-sm text-muted">使用注册手机号接收验证码。</p>

          <form className="mt-8 space-y-5">
            <div>
              <label htmlFor="phone" className="text-xs font-medium text-ink">
                手机号
              </label>
              <input
                id="phone"
                type="tel"
                inputMode="numeric"
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
                  placeholder="6 位验证码"
                  className="w-full rounded-sm border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-muted/70 focus:border-jade"
                />
                <button
                  type="button"
                  disabled
                  className="shrink-0 rounded-sm border border-line bg-surface px-3 text-xs text-muted"
                >
                  获取验证码
                </button>
              </div>
            </div>
            <button
              type="button"
              disabled
              className="w-full rounded-sm bg-ink px-4 py-3 text-sm font-medium text-paper/60"
            >
              登录（W6 开放）
            </button>
          </form>

          <div className="mt-6 rounded-sm border border-line bg-surface p-4 text-xs leading-6 text-muted">
            还没有邀请码？
            <Link href="/pricing" className="ml-1 text-jade-deep hover:underline">
              查看获取方式
            </Link>
            。本项目不提供微信登录与微信支付。
          </div>

          <p className="mt-6 text-xs leading-6 text-muted">
            登录即表示同意《用户协议》与《隐私政策》。我们仅收集手机号用于账号识别，不读取通讯录。
          </p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
