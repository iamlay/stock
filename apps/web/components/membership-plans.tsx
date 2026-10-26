import Link from "next/link";

import { CheckoutButtons } from "@/components/checkout-buttons";
import { planPrice, type MembershipPlan } from "@/lib/plans";

export function MembershipPlans({ plans, checkout = false, nextPath, selectedPlan, preferredPayment }: {
  plans: MembershipPlan[] | null;
  checkout?: boolean;
  nextPath?: string;
  selectedPlan?: string;
  preferredPayment?: "alipay" | "wxpay";
}) {
  if (!plans) {
    return <div className="card p-6 text-sm text-muted" role="status">
      套餐信息暂不可用，请稍后刷新。你仍可浏览基础数据。
    </div>;
  }
  return <div className="grid gap-4 md:grid-cols-2">
    {plans.map((plan) => <div
      key={plan.id}
      className={`card flex flex-col p-6 ${plan.purchasable ? "border-jade/50 bg-jade-soft/30" : ""}`}
    >
      <h2 className="text-lg font-medium text-ink">{plan.name}</h2>
      <p className="tnum mt-4 text-3xl font-semibold text-ink">{planPrice(plan)}</p>
      <p className="mt-2 text-xs leading-6 text-muted">{plan.billing_note}</p>
      <ul className="mt-5 flex-1 space-y-2.5 text-sm text-ink-soft">
        {plan.features.map((feature) => <li key={feature} className="flex gap-2">
          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-jade" />{feature}
        </li>)}
      </ul>
      {plan.purchasable && checkout ? <CheckoutButtons plan={plan} nextPath={nextPath}
        preferredPayment={selectedPlan === plan.id ? preferredPayment : undefined} /> : <Link
        href={plan.purchasable ? "/pricing" : "/login"}
        className="mt-6 block rounded-sm border border-line bg-surface px-4 py-2.5 text-center text-sm text-ink hover:border-ink"
      >{plan.purchasable ? "查看开通方式" : "注册 / 登录免费账号"}</Link>}
    </div>)}
  </div>;
}
