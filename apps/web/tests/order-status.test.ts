import assert from "node:assert/strict";
import test from "node:test";

import { parseOrderStatus, paymentReturnOrder, pollOrder, type OrderStatus } from "../lib/order-status";

const pending: OrderStatus = { order_no: "SL1", status: "pending", product: "standard-monthly",
  amount: 9.99, paid_at: null, delivered_at: null, plan_expires_at: "2099-01-01T00:00:00Z" };
const delivered: OrderStatus = { ...pending, status: "delivered",
  paid_at: "2026-10-26T00:00:00Z", delivered_at: "2026-10-26T00:00:00Z" };

test("return order must be singular and safe, not inferred from payment success flags", () => {
  assert.equal(paymentReturnOrder(new URLSearchParams("payment=return&order=SL1")), "SL1");
  for (const query of ["payment=return", "order=", "order=SL1&order=SL2", "order=../admin", "order=" + "x".repeat(65)]) {
    assert.equal(paymentReturnOrder(new URLSearchParams(query)), null);
  }
});

test("only matching orders with complete delivery timestamps confirm success", () => {
  assert.equal(parseOrderStatus(pending, "SL1").status, "pending");
  assert.equal(parseOrderStatus(delivered, "SL1").status, "delivered");
  for (const value of [null, {}, { ...delivered, order_no: "OTHER" },
    { ...delivered, delivered_at: null }, { ...delivered, paid_at: undefined },
    { ...delivered, status: "unknown" }, { ...delivered, amount: NaN }]) {
    assert.throws(() => parseOrderStatus(value, "SL1"));
  }
});

test("pending and paid continue polling until this order is delivered", async () => {
  const sequence: OrderStatus[] = [pending, { ...pending, status: "paid" }, delivered];
  const seen: string[] = [];
  const result = await pollOrder(async () => sequence.shift()!, new AbortController().signal,
    (order) => seen.push(order.status), { timeoutMs: 500, intervalMs: 1, requestTimeoutMs: 100 });
  assert.deepEqual(seen, ["pending", "paid"]);
  assert.equal(result.kind, "terminal");
  if (result.kind === "terminal") assert.equal(result.order.status, "delivered");
});

test("pending times out despite an existing future membership expiry", async () => {
  let calls = 0;
  const result = await pollOrder(async () => { calls++; return pending; }, new AbortController().signal,
    () => undefined, { timeoutMs: 30, intervalMs: 5, requestTimeoutMs: 10 });
  assert.equal(result.kind, "timeout");
  assert(calls > 0 && calls <= 10);
});

test("network, authorization, not-found and rate-limit failures stop automatic requests", async () => {
  for (const status of [undefined, 401, 403, 404, 429, 500]) {
    let calls = 0;
    const result = await pollOrder(async () => { calls++; throw Object.assign(new Error("failed"), { status }); },
      new AbortController().signal, () => undefined);
    assert.equal(result.kind, "error");
    assert.equal(calls, 1);
    if (result.kind === "error") assert.equal(result.status, status);
  }
});

test("refunded/closed/failed orders are terminal but never delivered", async () => {
  for (const status of ["refunded", "closed", "failed"] as const) {
    const result = await pollOrder(async () => ({ ...pending, status }), new AbortController().signal, () => undefined);
    assert.equal(result.kind, "terminal");
    if (result.kind === "terminal") assert.equal(result.order.status, status);
  }
});

test("unmount aborts a pending request without emitting a state update", async () => {
  const controller = new AbortController();
  const promise = pollOrder((signal) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
  }), controller.signal, () => assert.fail("unexpected update"));
  controller.abort();
  assert.deepEqual(await promise, { kind: "cancelled" });
});

test("a hung request is bounded and a later manual attempt can succeed", async () => {
  const signal = new AbortController().signal;
  const result = await pollOrder((requestSignal) => new Promise((_resolve, reject) => {
    requestSignal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
  }), signal, () => undefined, { timeoutMs: 500, intervalMs: 1, requestTimeoutMs: 5 });
  assert.equal(result.kind, "error");
  const retried = await pollOrder(async () => delivered, signal, () => undefined);
  assert.equal(retried.kind, "terminal");
});
