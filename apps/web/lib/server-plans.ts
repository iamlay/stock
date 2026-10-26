import { parseMembershipPlans, type MembershipPlan } from "./plans";

export async function loadMembershipPlans(): Promise<MembershipPlan[] | null> {
  const base = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${base}/api/v1/plans`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (!response.ok) return null;
    return parseMembershipPlans(await response.json());
  } catch {
    return null;
  }
}
