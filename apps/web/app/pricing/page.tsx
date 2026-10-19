import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/chrome";

export const metadata: Metadata = { title: "会员与兑换" };

type Plan = {
  name: string;
  price: string;
  original?: string;
  note: string;
  features: string[];
  cta: string;
  highlight: boolean;
};

const plans: Plan[] = [
  {
    name: "7 天试用",
    price: "¥0",
    note: "邀请码开通",
    features: ["今日市场与 ETF 数据", "策略回测 5 次/日", "基础估值与份额数据", "到期自动降级"],
    cta: "使用邀请码",
    highlight: false,
  },
  {
    name: "标准年付",
    price: "¥199",
    original: "¥299",
    note: "早鸟价 · 第三方平台购买",
    features: ["全部行情与 ETF 数据", "策略回测 20 次/日", "回测明细导出", "会员社群", "到期前提醒"],
    cta: "获取兑换码",
    highlight: true,
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main>
        <section className="border-b border-line">
          <div className="mx-auto max-w-6xl px-6 py-14">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-jade">Membership</p>
            <h1 className="mt-3 font-serif text-4xl text-ink">会员与兑换</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-soft">
              内测阶段不开放公开注册，站内也不接入在线支付。会员通过第三方平台购买后获得兑换码，在站内兑换开通。
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-12">
          <div className="grid gap-4 md:grid-cols-2">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`card flex flex-col p-6 ${plan.highlight ? "border-jade/50 bg-jade-soft/30" : ""}`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-medium text-ink">{plan.name}</h2>
                    <p className="mt-1 text-xs text-muted">{plan.note}</p>
                  </div>
                  {plan.highlight ? (
                    <span className="rounded-sm bg-jade px-2 py-1 text-[11px] text-white">推荐</span>
                  ) : null}
                </div>
                <p className="tnum mt-6 text-3xl font-semibold text-ink">
                  {plan.price}
                  {plan.original ? (
                    <span className="ml-2 text-sm font-normal text-muted line-through">
                      {plan.original}
                    </span>
                  ) : null}
                </p>
                <ul className="mt-6 space-y-2.5 text-sm text-ink-soft">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-jade" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  disabled
                  className={`mt-8 w-full rounded-sm px-4 py-2.5 text-sm font-medium ${
                    plan.highlight
                      ? "bg-ink text-paper/70"
                      : "border border-line bg-surface text-ink/50"
                  }`}
                >
                  {plan.cta}（即将开放）
                </button>
              </div>
            ))}
          </div>

          <div className="mt-12 grid gap-6 lg:grid-cols-3">
            {[
              ["01", "第三方平台购买", "在知识星球 / 小鹅通年费专栏完成支付，平台代收并开具凭证。"],
              ["02", "获取兑换码", "支付成功后由平台自动发货或人工发放兑换码，一码一用。"],
              ["03", "站内兑换开通", "登录后输入兑换码，立即开通对应时长；到期前站内信提醒。"],
            ].map(([step, title, body]) => (
              <div key={step} className="card p-5">
                <span className="tnum text-xs text-muted">{step}</span>
                <h3 className="mt-3 text-sm font-medium text-ink">{title}</h3>
                <p className="mt-2 text-xs leading-6 text-muted">{body}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 rounded-sm border border-line bg-surface p-5 text-sm leading-6 text-ink-soft">
            <p className="font-medium text-ink">关于支付与登录</p>
            <p className="mt-2 text-xs leading-6 text-muted">
              本项目不提供微信登录、微信支付或支付宝直连。所有交易由第三方知识付费平台承接，站内仅负责兑换与权益发放。这样可以在没有经营主体的阶段，仍然合规地验证付费意愿。
            </p>
          </div>

          <div className="mt-8 text-sm">
            <Link href="/login" className="text-jade-deep hover:underline">
              已有邀请码或兑换码？去登录 →
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
