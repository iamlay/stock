import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/chrome";
import { MembershipSummary } from "@/components/membership-summary";
import { LoginForm } from "@/components/login-form";
import { safeReturnPath, withReturnPath } from "@/lib/return-path";

export const metadata: Metadata = { title: "登录" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const next = safeReturnPath((await searchParams).next);
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto grid max-w-6xl gap-10 px-6 py-14 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="hidden rounded-sm bg-ink p-8 text-paper lg:block">
          <p className="text-xs uppercase tracking-[0.18em] text-jade">Email First</p>
          <h1 className="mt-6 font-serif text-3xl leading-snug">
            邮箱注册，
            <br />
            按需开通会员。
          </h1>
          <p className="mt-4 text-sm leading-6 text-paper/70">
            当前使用邮箱和密码注册，完成邮箱验证后才能登录。手机号验证码登录保留，待短信服务接入后开放。
          </p>
          <ul className="mt-10 space-y-4 text-sm text-paper/80">
            {["邮箱 + 密码，注册后验证邮箱", "基础数据免费，回测按日限额", "支付宝 / 微信支付，也可使用会员兑换码"].map(
              (item) => (
                <li key={item} className="flex items-center gap-3 border-b border-white/10 pb-4">
                  <span className="h-1.5 w-1.5 rounded-full bg-jade" />
                  {item}
                </li>
              ),
            )}
          </ul>
          <p className="mt-10 text-xs leading-6 text-paper/50">
            手机号验证码登录仍在代码中保留，生产环境默认关闭，后续接入短信服务商即可启用。
          </p>
        </section>

        <section className="mx-auto w-full max-w-md">
          <p className="text-xs text-muted">StockLab 工作台</p>
          <h2 className="mt-2 font-serif text-3xl text-ink">登录 / 注册</h2>
          <p className="mt-2 text-sm text-muted">使用邮箱和密码，或手机号验证码。</p>

          <LoginForm next={next} />

          <div className="mt-6 rounded-sm border border-line bg-surface p-4 text-xs leading-6 text-muted">
            邀请码仅用于注册准入；会员兑换码用于开通权益。
            <Link href={withReturnPath("/pricing", next)} className="ml-1 text-jade-deep hover:underline">
              查看会员与支付方式
            </Link>
            <MembershipSummary />
          </div>

          <p className="mt-6 text-xs leading-6 text-muted">
            登录即表示同意
            <Link href="/legal/terms" className="mx-1 text-jade-deep hover:underline">
              《用户协议》
            </Link>
            与
            <Link href="/legal/privacy" className="mx-1 text-jade-deep hover:underline">
              《隐私政策》
            </Link>
            。我们仅收集邮箱/手机号用于账号识别。
          </p>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
