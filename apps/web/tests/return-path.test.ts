import assert from "node:assert/strict";
import test from "node:test";

import { safeReturnPath, withReturnPath } from "../lib/return-path";

test("returns to pricing and preserves a research task's query and hash", () => {
  for (const path of [
    "/",
    "/pricing",
    "/pricing?plan=standard-monthly#checkout",
    "/stocks/600036?tab=grid",
    "/strategies/dual-ma?code=510300&start=2020-01-01",
    "/stocks?q=%E9%93%B6%E8%A1%8C",
  ]) {
    assert.equal(safeReturnPath(path), path);
  }
});

test("rejects external destinations, encoded bypasses and non-product endpoints", () => {
  for (const path of [
    undefined, null, ["/pricing", "//evil.example"], "", "pricing",
    "https://evil.example/pricing", "//evil.example/pricing", "javascript:alert(1)",
    "/\\evil.example", "/%2fevil.example", "/%252fevil.example",
    "/pricing%2f%2fevil.example", "/pricing%5cevil.example",
    "/pricing%0a", "/pricing\n", "/pricing\t", "/pricing%", "/pricing%252f",
    "/api/session", "/login?next=/pricing", "/verify-email?token=x", "/admin/orders",
    "/pricing/../../api/session", `/pricing?${"x".repeat(2048)}`,
  ]) {
    assert.equal(safeReturnPath(path), "/account", String(path));
  }
});

test("keeps the destination through registration, verification and login URLs", () => {
  const destination = "/pricing?plan=standard-monthly#checkout";
  for (const page of [
    "/verify-email/sent?email=user%40example.com",
    "/verify-email?token=verification-token",
    "/login",
  ]) {
    const url = new URL(withReturnPath(page, destination), "https://stocklab.invalid");
    assert.equal(safeReturnPath(url.searchParams.get("next")), destination);
    if (page.includes("email=")) assert.equal(url.searchParams.get("email"), "user@example.com");
    if (page.includes("token=")) assert.equal(url.searchParams.get("token"), "verification-token");
  }
  assert.equal(withReturnPath("/login", "//evil.example"), "/login?next=%2Faccount");
});

test("purchase selection survives nested verification without requesting payment", async () => {
  const { checkoutResumePath } = await import("../lib/return-path");
  const source = "/stocks/600036?tab=grid#yield";
  const resume = checkoutResumePath("standard-monthly", "wxpay", source);
  const login = new URL(withReturnPath("/login", resume), "https://stocklab.invalid");
  const verify = new URL(withReturnPath("/verify-email?token=x", login.searchParams.get("next")), "https://stocklab.invalid");
  const restored = new URL(safeReturnPath(verify.searchParams.get("next")), "https://stocklab.invalid");
  assert.equal(restored.pathname, "/pricing");
  assert.equal(restored.searchParams.get("next"), source);
  assert.equal(restored.searchParams.get("plan"), "standard-monthly");
  assert.equal(restored.searchParams.get("payment"), "wxpay");
  assert.equal(restored.hash, "#checkout");
  const invalid = new URL(checkoutResumePath("standard-monthly", "alipay", "//evil.example"), "https://stocklab.invalid");
  assert.equal(invalid.searchParams.get("next"), "/account");
});

test("strategy returns restore inputs but cannot replay a calculation", () => {
  assert.equal(safeReturnPath("/strategies/dual-ma?code=510300&run=1&fast=10&run=1#result"),
    "/strategies/dual-ma?code=510300&fast=10#result");
  assert.equal(safeReturnPath("/strategies/dual-ma?%72un=1"), "/strategies/dual-ma");
});
