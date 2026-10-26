import assert from "node:assert/strict";
import test from "node:test";
import { alertDraftPath, alertUpdate, isWatchlistLimit, readAlertDraft, readWatchlistFilters, taskDestination, watchlistTaskPath } from "../lib/task-context";
import { checkoutResumePath, withReturnPath } from "../lib/return-path";

const draft = { price_pct: 7.5, dividend: false, email: true, grid: true, grid_yield: 5.5, resonance: true };

test("alert draft survives pricing and login without an instruction to save", () => {
  const target = alertDraftPath(draft);
  const checkout = checkoutResumePath("standard-monthly", "alipay", target);
  const login = new URL(withReturnPath("/login", checkout), "https://test.invalid");
  const resumed = new URL(login.searchParams.get("next")!, login.origin);
  const task = taskDestination(resumed.searchParams)!;
  assert.equal(task.href, target);
  assert.equal(task.label, "返回提醒设置，确认并保存");
  assert.deepEqual(readAlertDraft(new URL(task.href, login.origin).searchParams), draft);
});

test("invalid and ambiguous drafts do not replace saved settings", () => {
  assert.deepEqual(readAlertDraft(new URLSearchParams("grid=1")), {});
  assert.deepEqual(readAlertDraft(new URLSearchParams("draft=alerts&draft=alerts&grid=1")), {});
  assert.deepEqual(readAlertDraft(new URLSearchParams("draft=alerts&price_pct=Infinity&grid_yield=999&grid=yes&email=1&email=0")), {});
  assert.deepEqual(readAlertDraft(new URLSearchParams("draft=alerts&price_pct=0&grid_yield=4.2&dividend=0")), { dividend: false });
});

test("free reminder saves exclude all premium parameters", () => {
  assert.deepEqual(alertUpdate(draft, false), { price_pct: 7.5, dividend: false, email: true });
  assert.deepEqual(alertUpdate(draft, true), draft);
});

test("watchlist filters travel together including Chinese group names", () => {
  for (const stockSort of ["yield", "rly", "percentile", "bollinger", "cap", "name"]) {
    const filters = { etfSort: "aum", stockSort, etfGroup: "低估 ETF", stockGroup: "高股息", onlyResonance: true, onlyLowValue: false };
    assert.deepEqual(readWatchlistFilters(new URL(watchlistTaskPath(filters), "https://test.invalid").searchParams), filters);
  }
  assert.deepEqual(readWatchlistFilters(new URLSearchParams("wl_stockSort=unknown&wl_etfSort=aum&wl_etfSort=name&wl_onlyResonance=true&wl_stockGroup=%00")), {});
});

test("task destinations reject external and duplicate next, and remove run", () => {
  for (const next of ["https://evil.invalid", "//evil.invalid", "/api/delete", "/account"]) {
    assert.equal(taskDestination(new URLSearchParams({ next })), null);
  }
  assert.equal(taskDestination(new URLSearchParams("next=/stocks&next=/watchlist")), null);
  const result = taskDestination(new URLSearchParams({ next: "/strategies/grid?code=510300&run=1&start=2025-01-01#result" }))!;
  assert.equal(result.href, "/strategies/grid?code=510300&start=2025-01-01#result");
  assert.equal(taskDestination(new URLSearchParams({ next: "/account#history" }))?.label, "返回查看回测历史");
});

test("only the actual watchlist capacity error triggers an upgrade prompt", () => {
  const error = Object.assign(new Error("免费用户最多 10 个自选，开通会员可无限添加"), { status: 403 });
  assert.equal(isWatchlistLimit(error), true);
  assert.equal(isWatchlistLimit(new Error(error.message)), false);
  assert.equal(isWatchlistLimit(Object.assign(new Error("邮箱未验证"), { status: 403 })), false);
  assert.equal(isWatchlistLimit(Object.assign(new Error(error.message), { status: 500 })), false);
});
