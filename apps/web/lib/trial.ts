export type Entitlements = {
  state: "guest" | "free" | "trial" | "member";
  source: string;
  expires_at: string | null;
  trial_used: boolean;
  trial_eligible: boolean;
  capabilities: {
    advanced_data: boolean;
    history: boolean;
    advanced_alerts: boolean;
    unlimited_backtests: boolean;
    unlimited_watchlist: boolean;
  };
  daily_backtest_limit: number | null;
};

type TrialProfile = {
  email: string | null;
  email_verified: boolean;
  entitlements?: Entitlements;
};

// Missing/old API responses must never turn into an offer or activation success.
export function trialState(profile: TrialProfile, now = Date.now()) {
  const rights = profile.entitlements;
  if (!rights) return "unavailable";
  const expires = rights.expires_at ? Date.parse(rights.expires_at) : NaN;
  if (rights.state === "member") return "member";
  if (rights.state === "trial") {
    if (!Number.isFinite(expires)) return "unavailable";
    return expires > now ? "active" : "expired";
  }
  if (rights.trial_used) return "used";
  if (!profile.email || !profile.email_verified) return "unverified";
  return rights.trial_eligible ? "eligible" : "unavailable";
}

export function trialExpiry(value: string | null): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "待确认";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(new Date(value)) + "（北京时间）";
}
