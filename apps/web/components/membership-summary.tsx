"use client";

import { useEffect, useState } from "react";
import { parseMembershipPlans, planPrice, type MembershipPlan } from "@/lib/plans";

/** Use the same server catalogue as pricing; never keep a local price/benefit fallback. */
export function MembershipSummary() {
  const [plans, setPlans] = useState<MembershipPlan[] | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/plans", { cache: "no-store", signal: controller.signal })
      .then(async (response) => response.ok ? parseMembershipPlans(await response.json()) : null)
      .then((value) => { if (!controller.signal.aborted) setPlans(value); })
      .catch(() => undefined)
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  const member = plans?.find((plan) => plan.purchasable);
  if (!member) return <p className="mt-3 text-xs leading-6 text-muted" role="status">
    {loading ? "正在加载会员权益…" : "套餐信息暂不可用，请稍后前往会员页查看。"}
  </p>;
  return <div className="mt-3 space-y-2 text-sm leading-6 text-ink-soft">
    <p>{member.name} · <span className="tnum font-medium">{planPrice(member)}</span></p>
    <p className="text-xs text-muted">{member.billing_note}；支持支付宝 / 微信，也可使用会员兑换码。</p>
    <p className="text-xs text-muted">{member.features.join("；")}。</p>
  </div>;
}
