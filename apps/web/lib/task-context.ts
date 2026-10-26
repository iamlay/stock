import { safeReturnPath } from "./return-path";

export type AlertDraft = {
  price_pct: number; dividend: boolean; email: boolean;
  grid: boolean; grid_yield: number; resonance: boolean;
};
const GRID_YIELDS = [4, 4.5, 5, 5.5, 6];

/** URLs contain only a bounded settings draft, never an instruction to save. */
export function readAlertDraft(query: URLSearchParams): Partial<AlertDraft> {
  const draft: Partial<AlertDraft> = {};
  if (query.getAll("draft").length !== 1 || query.get("draft") !== "alerts") return draft;
  for (const key of ["dividend", "email", "grid", "resonance"] as const) {
    const values = query.getAll(key);
    if (values.length === 1 && (values[0] === "1" || values[0] === "0")) draft[key] = values[0] === "1";
  }
  for (const key of ["price_pct", "grid_yield"] as const) {
    const values = query.getAll(key);
    if (values.length !== 1 || !/^\d+(\.\d+)?$/.test(values[0])) continue;
    const value = Number(values[0]);
    if (key === "price_pct" ? value >= 1 && value <= 20 : GRID_YIELDS.includes(value)) draft[key] = value;
  }
  return draft;
}

export function alertDraftPath(draft: AlertDraft): string {
  const query = new URLSearchParams({ draft: "alerts" });
  for (const [key, value] of Object.entries(draft)) query.set(key, typeof value === "boolean" ? (value ? "1" : "0") : String(value));
  return `/notifications?${query}#settings`;
}

export function alertUpdate(draft: AlertDraft, premium: boolean): Partial<AlertDraft> {
  const basic = { price_pct: draft.price_pct, dividend: draft.dividend, email: draft.email };
  return premium ? { ...draft } : basic;
}

export function taskDestination(query: URLSearchParams): { href: string; label: string } | null {
  const values = query.getAll("next");
  if (values.length !== 1) return null;
  const href = safeReturnPath(values[0]);
  if (href === "/account") return null;
  const url = new URL(href, "https://stocklab.invalid");
  const label = url.pathname === "/notifications" ? "返回提醒设置，确认并保存"
    : url.pathname === "/account" && url.hash === "#history" ? "返回查看回测历史"
    : url.pathname.startsWith("/strategies/") ? "返回策略，确认参数后运行"
    : /^\/(stocks|etf)\/\d{6}$/.test(url.pathname) ? `返回 ${url.pathname.split("/").pop()} 继续研究`
    : url.pathname === "/watchlist" ? "返回自选，继续筛选与跟踪"
    : "返回原页面继续研究";
  return { href, label };
}

export function isWatchlistLimit(error: unknown): boolean {
  return error instanceof Error && "status" in error && error.status === 403 && /^免费用户最多 \d+ 个自选/.test(error.message);
}

export type WatchlistFilters = {
  etfSort: string; stockSort: string; etfGroup: string; stockGroup: string;
  onlyResonance: boolean; onlyLowValue: boolean;
};

export function readWatchlistFilters(query: URLSearchParams): Partial<WatchlistFilters> {
  const filters: Partial<WatchlistFilters> = {};
  for (const key of ["etfSort", "stockSort", "etfGroup", "stockGroup", "onlyResonance", "onlyLowValue"] as const) {
    const values = query.getAll(`wl_${key}`);
    if (values.length !== 1) continue;
    const value = values[0];
    if (key === "onlyResonance" || key === "onlyLowValue") {
      if (value === "1" || value === "0") filters[key] = value === "1";
    } else if (key === "etfGroup" || key === "stockGroup") {
      if (value.length > 0 && value.length <= 32 && !/[\u0000-\u001f\u007f]/.test(value)) filters[key] = value;
    } else {
      const allowed = key === "etfSort" ? ["default", "change", "aum", "name"] : ["yield", "rly", "percentile", "bollinger", "cap", "name"];
      if (allowed.includes(value)) filters[key] = value;
    }
  }
  return filters;
}

export function watchlistTaskPath(filters: WatchlistFilters): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) query.set(`wl_${key}`, typeof value === "boolean" ? (value ? "1" : "0") : value);
  return safeReturnPath(`/watchlist?${query}`);
}
