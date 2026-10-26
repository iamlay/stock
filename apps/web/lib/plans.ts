export type MembershipPlan = {
  id: string;
  name: string;
  price_cny: number;
  duration_days: number;
  features: string[];
  purchasable: boolean;
  purchase_channel: string;
  billing_note: string;
};

// Reject outdated/incomplete responses rather than rendering a stale price or trial offer.
export function parseMembershipPlans(value: unknown): MembershipPlan[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const valid = value.every((plan) =>
    plan && typeof plan.id === "string" && typeof plan.name === "string" &&
    typeof plan.price_cny === "number" && Number.isFinite(plan.price_cny) && plan.price_cny >= 0 &&
    Number.isInteger(plan.duration_days) && plan.duration_days >= 0 &&
    Array.isArray(plan.features) && plan.features.every((feature: unknown) => typeof feature === "string") &&
    typeof plan.purchasable === "boolean" && typeof plan.purchase_channel === "string" &&
    typeof plan.billing_note === "string" &&
    (!plan.purchasable || (plan.price_cny > 0 && plan.duration_days > 0)),
  );
  if (!valid || new Set(value.map((plan) => plan.id)).size !== value.length) return null;
  return value;
}

export function planPrice(plan: MembershipPlan): string {
  return `¥${plan.price_cny === 0 ? "0" : plan.price_cny.toFixed(2)}${
    plan.duration_days > 0 ? `/${plan.duration_days} 天` : ""
  }`;
}
