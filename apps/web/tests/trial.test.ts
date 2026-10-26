import assert from "node:assert/strict";
import test from "node:test";

import { trialExpiry, trialState, type Entitlements } from "../lib/trial";

const now = Date.parse("2026-10-26T08:00:00Z");
const rights: Entitlements = {
  state: "free", source: "free", expires_at: null, trial_used: false, trial_eligible: true,
  capabilities: { advanced_data: false, history: false, advanced_alerts: false,
    unlimited_backtests: false, unlimited_watchlist: false }, daily_backtest_limit: 50,
};
function profile(changes: Partial<Entitlements> = {}) {
  return { email: "test@example.com", email_verified: true, entitlements: { ...rights, ...changes } };
}

test("only verified, server-eligible accounts receive the trial action", () => {
  assert.equal(trialState(profile(), now), "eligible");
  assert.equal(trialState({ ...profile(), email_verified: false }, now), "unverified");
  assert.equal(trialState({ ...profile(), email: null }, now), "unverified");
  assert.equal(trialState(profile({ trial_eligible: false }), now), "unavailable");
  assert.equal(trialState({ email: "test@example.com", email_verified: true }, now), "unavailable");
});

test("active, expired and consumed trials never offer another claim", () => {
  assert.equal(trialState(profile({ state: "trial", expires_at: "2026-10-27T08:00:00Z" }), now), "active");
  assert.equal(trialState(profile({ state: "trial", expires_at: "2026-10-26T08:00:00Z" }), now), "expired");
  assert.equal(trialState(profile({ trial_used: true }), now), "used");
  assert.equal(trialState(profile({ state: "trial", expires_at: null }), now), "unavailable");
  assert.equal(trialState(profile({ state: "trial", expires_at: "invalid" }), now), "unavailable");
});

test("paid membership takes priority over historical trial status", () => {
  assert.equal(trialState(profile({ state: "member", trial_used: true }), now), "member");
});

test("expiry preserves time of day and an explicit timezone", () => {
  assert.match(trialExpiry("2026-10-26T08:12:34Z"), /16:12:34.*北京时间/);
  assert.equal(trialExpiry(null), "待确认");
  assert.equal(trialExpiry("invalid"), "待确认");
});
