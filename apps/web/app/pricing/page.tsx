import type { Metadata } from "next";
import Link from "next/link";

import { CheckoutButtons } from "@/components/checkout-buttons";
import { SiteFooter, SiteHeader } from "@/components/chrome";

export const metadata: Metadata = { title: "会员与在线支付" };

type Plan = {
  id: string;
  name: string;
  price: string;
  original?: string;
  note: string;
  features: string[];
  cta: string;
  highlight: boolean;
  purchasable: boolean;
};

const plans: Plan[] = [
  {
    id: "trial",
    name: "7 天试用",
    price: "¥0",
    note: "邀请码开通",
    features: ["今日市场与 ETF 数据", "策略回测 5 次/日", "基础估值与份额数据", "到期自动降级"],
    cta: "使用邀请码",
    highlight: false,
    purchasable: false,
  },
  {
    id: "standard-monthly",
    name: "标准月付",
    price: "¥9.99",
    note: "9.99 元/月 · 支付宝 / 微信",
    features: [
      "股息网格 / 布林 / 财务",
      "自选不限数量",
      "网格提醒 / 共振提醒",
      "回测历史与导出",
    ],
    cta: "立即开通",
    highlight: true,
    purchasable: true,
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
            <h1 className="mt-3 font-serif text-4xl text-ink">会员与在线支付</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-soft">
              支持支付宝 / 微信在线支付，支付成功后会员权益自动到账。也可以继续使用邀请码或兑换码开通。
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
                {plan.purchasable ? (
                  <CheckoutButtons planId={plan.id} />
                ) : (
                  <Link
                    href="/login"
                    className="mt-8 block w-full rounded-sm border border-line bg-surface px-4 py-2.5 text-center text-sm font-medium text-ink-soft hover:border-ink hover:text-ink"
                  >
                    {plan.cta}
                  </Link>
                )}
              </div>
            ))}
          </div>

          <div className="mt-10 grid gap-6 lg:grid-cols-3">
            {[
              ["01", "扫码或跳转支付", "支持支付宝与微信支付，支付页面由易支付通道承接。"],
              ["02", "自动开通", "支付成功后异步回调验签，会员权益自动到账。"],
              ["03", "个人中心确认", "返回个人中心查看会员状态与有效期；未到账可刷新重试。"],
            ].map(([step, title, body]) => (
              <div key={step} className="card p-5">
                <span className="tnum text-xs text-muted">{step}</span>
                <h3 className="mt-3 text-sm font-medium text-ink">{title}</h3>
                <p className="mt-2 text-xs leading-6 text-muted">{body}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 overflow-hidden rounded-sm border border-line bg-surface">
            <div className="border-b border-line px-5 py-4">
              <h2 className="text-sm font-medium text-ink">权限边界</h2>
              <p className="mt-1 text-xs text-muted">免费账号可用基础数据；高级股息工具属于会员权益。</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="border-b border-line text-xs text-muted">
                  <tr>
                    <th className="px-5 py-3 font-normal">功能</th>
                    <th className="px-5 py-3 text-center font-normal">免费</th>
                    <th className="px-5 py-3 text-center font-normal">会员</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line text-xs">
                  {[
                    ["ETF / 个股基础数据", "可用", "可用"],
                    ["个股自选", "最多 10 个", "不限"],
                    ["涨跌 / 除息提醒", "可用", "可用"],
                    ["股息网格 / 布林 / 财务", "—", "可用"],
                    ["网格提醒", "—", "可用"],
                    ["回测历史 / 导出", "—", "可用"],
                  ].map(([feature, free, member]) => (
                    <tr key={feature}>
                      <td className="px-5 py-3 text-ink-soft">{feature}</td>
                      <td className="px-5 py-3 text-center text-muted">{free}</td>
                      <td className="px-5 py-3 text-center text-jade-deep">{member}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-10 rounded-sm border border-line bg-surface p-5 text-sm leading-6 text-ink-soft">
            <p className="font-medium text-ink">关于支付与登录</p>
            <p className="mt-2 text-xs leading-6 text-muted">
              支付通道为易支付，支持支付宝和微信。站内不保存银行卡信息，也不接入微信登录。
              支付结果以异步回调验签为准；兑换码通道继续保留。
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
