import { loadMembershipPlans } from "@/lib/server-plans";

export async function GET() {
  const plans = await loadMembershipPlans();
  return Response.json(plans ?? { error: "套餐信息暂不可用" }, {
    status: plans ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  });
}
