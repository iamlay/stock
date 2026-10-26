import assert from "node:assert/strict";
import test from "node:test";

import { parseMembershipPlans, planPrice, type MembershipPlan } from "../lib/plans";
import { loadMembershipPlans } from "../lib/server-plans";

const offer: MembershipPlan = {
  id: "member-example", name: "示例会员", price_cny: 17.25, duration_days: 45,
  features: ["服务端提供的权益"], purchasable: true, purchase_channel: "ezfpy",
  billing_note: "一次购买 45 天，不自动扣费",
};

test("formats the returned price and duration without a local monthly offer", () => {
  assert.equal(planPrice(offer), "¥17.25/45 天");
  assert.deepEqual(parseMembershipPlans([offer]), [offer]);
});

test("does not accept partial, outdated or invalid catalogue data", () => {
  const { billing_note: _, ...oldOffer } = offer;
  for (const value of [null, {}, [], [oldOffer], [offer, offer],
    [{ ...offer, price_cny: -1 }], [{ ...offer, price_cny: "9.99" }],
    [{ ...offer, duration_days: 0 }], [{ ...offer, features: [42] }]]) {
    assert.equal(parseMembershipPlans(value), null);
  }
});

test("loads the upstream catalogue without caching and fails closed on errors", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async (_url: string, options: RequestInit) => {
    assert.equal(options.cache, "no-store");
    return Response.json([offer]);
  });
  assert.deepEqual(await loadMembershipPlans(), [offer]);
  mock.mock.mockImplementation(async () => new Response("offline", { status: 503 }));
  assert.equal(await loadMembershipPlans(), null);
  mock.mock.mockImplementation(async () => { throw new Error("network unavailable"); });
  assert.equal(await loadMembershipPlans(), null);
  mock.mock.mockImplementation(async () => Response.json([{ ...offer, billing_note: undefined }]));
  assert.equal(await loadMembershipPlans(), null);
});
