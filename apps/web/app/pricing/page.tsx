import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/chrome";
import { MembershipPlans } from "@/components/membership-plans";
import { safeReturnPath } from "@/lib/return-path";
import { loadMembershipPlans } from "@/lib/server-plans";

export const metadata: Metadata = { title: "会员与在线支付" };

export default async function PricingPage({ searchParams }: {
  searchParams: Promise<{ next?: string | string[]; plan?: string | string[]; payment?: string | string[] }>;
}) {
  const params = await searchParams;
  const nextPath = safeReturnPath(params.next);
  const selectedPlan = typeof params.plan === "string" ? params.plan : undefined;
  const preferredPayment = params.payment === "alipay" || params.payment === "wxpay" ? params.payment : undefined;
  const plans = await loadMembershipPlans();
  return <div className="min-h-screen">
    <SiteHeader />
    <main>
      <section className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">Membership</p>
          <h1 className="mt-3 font-serif text-4xl text-ink">会员与在线支付</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-soft">
            先用免费基础功能，再按需要开通会员。支持支付宝 / 微信支付和会员兑换码，不自动扣费。
          </p>
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-6 py-12">
        <div id="checkout" className="scroll-mt-6">
          <MembershipPlans plans={plans} checkout nextPath={nextPath} selectedPlan={selectedPlan} preferredPayment={preferredPayment} />
        </div>
        {nextPath !== "/account" ? <Link href={nextPath} className="mt-4 inline-block text-sm text-jade-deep underline">返回原页面继续研究 →</Link> : null}
        <div className="mt-6 rounded-sm border border-line bg-surface p-5 text-sm leading-6">
          <p className="text-ink-soft">想先了解高级功能？登录后可在个人中心查看体验资格。需验证邮箱，每个账号仅一次，主动领取才开始计时。</p>
          <Link href="/account#trial" className="mt-2 inline-block text-jade-deep underline">查看体验资格 →</Link>
        </div>
        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          {[
            ["01", "选择支付方式", "登录后选择支付宝或微信，前往易支付收银台完成付款。"],
            ["02", "确认开通", "支付确认后自动开通会员，可在个人中心查看状态与有效期。"],
            ["03", "按需续费", "有效会员再次购买时叠加时长；到期不会自动扣费。"],
          ].map(([step, title, body]) => <div key={step} className="card p-5">
            <span className="tnum text-xs text-muted">{step}</span>
            <h2 className="mt-3 text-sm font-medium text-ink">{title}</h2>
            <p className="mt-2 text-xs leading-6 text-muted">{body}</p>
          </div>)}
        </div>
        <div className="mt-10 space-y-3 rounded-sm border border-line bg-surface p-5 text-sm leading-6 text-ink-soft">
          <h2 className="font-medium text-ink">开通与售后说明</h2>
          <p>邀请码仅用于注册准入，不会自动开通会员。已有会员兑换码，可登录后在个人中心兑换。</p>
          <p>支付由易支付通道承接，站内不保存银行卡信息或支付密码，也不提供微信登录。</p>
          <p>如付款后未到账，请稍后刷新个人中心；仍有疑问，可通过用户协议中的联系方式提供订单号协助核查。</p>
          <p>退款及发票请购买前联系核实适用条件；目前需人工处理，不提供自动退款。</p>
          <Link href="/legal/terms" className="inline-block text-jade-deep hover:underline">查看用户协议与联系方式 →</Link>
        </div>
        <div className="mt-8 text-sm">
          <Link href="/login?next=/account" className="text-jade-deep hover:underline">已有会员兑换码？登录后兑换 →</Link>
        </div>
      </section>
    </main>
    <SiteFooter />
  </div>;
}
