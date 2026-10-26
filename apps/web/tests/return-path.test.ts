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
