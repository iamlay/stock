import type { ApiEtf, BacktestResult } from "@/lib/api";
import type { Stock } from "@/lib/stocks";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "stocklab.token";

export type Me = {
  id: number;
  phone: string | null;
  email: string | null;
  email_verified: boolean;
  role: string;
  plan: string;
  plan_expires_at: string | null;
  is_member: boolean;
};

export type HistoryItem = {
  id: number;
  code: string;
  strategy: string;
  total_return: number;
  created_at: string;
};

export type AdminCode = {
  code: string;
  plan: string;
  duration_days: number;
  channel: string;
  batch_id: string | null;
  max_uses: number;
  used_count: number;
  status: string;
  expires_at: string | null;
  created_at: string;
  redeemed_at: string | null;
};

export type AdminCodeStats = {
  total: number;
  issued: number;
  redeemed: number;
  expired: number;
  revoked: number;
};

export type BatchSummary = {
  batch_id: string;
  channel: string;
  total: number;
  issued: number;
  redeemed: number;
  created_at: string;
};

export type AuditLog = {
  id: number;
  user_id: number | null;
  action: string;
  target_type: string;
  target_id: string | null;
  detail: Record<string, unknown>;
  ip: string | null;
  created_at: string;
};

export type AdminOrder = {
  id: number;
  order_no: string;
  platform: string;
  external_order_id: string | null;
  buyer_phone: string | null;
  buyer_email: string | null;
  user_id: number | null;
  product: string;
  amount: number;
  status: string;
  note: string | null;
  created_at: string;
  paid_at: string | null;
  delivered_at: string | null;
  refunded_at: string | null;
  code: string | null;
};

export type AdminUser = {
  id: number;
  email: string | null;
  phone: string | null;
  role: string;
  plan: string;
  plan_expires_at: string | null;
  status: string;
  email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type AdminBacktestSummary = {
  id: number;
  code: string;
  strategy: string;
  total_return: number;
  trades: number;
  status: string;
  created_at: string;
};

export type AdminUserDetail = {
  user: AdminUser;
  orders: AdminOrder[];
  codes: AdminCode[];
  backtests: AdminBacktestSummary[];
  orders_total: number;
  codes_total: number;
  backtests_total: number;
};

export type AdminOrderPage = {
  items: AdminOrder[];
  total: number;
  page: number;
  page_size: number;
};

export type AdminCodePage = {
  items: AdminCode[];
  total: number;
  page: number;
  page_size: number;
};

export type AdminBacktestPage = {
  items: AdminBacktestSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type AdminBacktestDetail = {
  id: number;
  created_at: string;
  result: BacktestResult;
};

export type AdminInvite = {
  code: string;
  batch_id: string | null;
  max_uses: number;
  used_count: number;
  bound_email: string | null;
  bound_phone: string | null;
  status: string;
  note: string | null;
  expires_at: string | null;
  created_at: string;
};

export type AdminInviteStats = {
  total: number;
  issued: number;
  redeemed: number;
  expired: number;
  revoked: number;
};

export type AdminInviteBatch = {
  batch_id: string;
  note: string | null;
  total: number;
  issued: number;
  redeemed: number;
  expired: number;
  revoked: number;
  created_at: string;
};

export type AdminInviteUsage = {
  id: number;
  code: string;
  user_id: number | null;
  email: string | null;
  phone: string | null;
  ip: string | null;
  created_at: string;
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = "请求失败";
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail ?? message;
    } catch {
      // ignore
    }
    if (response.status === 401) clearToken();
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function sendSms(phone: string): Promise<{ dev_code?: string }> {
  return request<{ dev_code?: string }>("/api/v1/auth/sms-code", {
    method: "POST",
    body: JSON.stringify({ phone }),
  });
}

export async function login(phone: string, code: string): Promise<Me> {
  const result = await request<{ access_token: string; user: Me }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ phone, code }),
  });
  setToken(result.access_token);
  return result.user;
}

export async function emailLogin(email: string, password: string): Promise<Me> {
  const result = await request<{ access_token: string; user: Me }>(
    "/api/v1/auth/login/email",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
  );
  setToken(result.access_token);
  return result.user;
}

export async function registerEmail(
  email: string,
  password: string,
  inviteCode?: string,
  phone?: string,
): Promise<{
  email: string;
  verificationSent: boolean;
  devVerificationToken: string | null;
}> {
  return request<{
    email: string;
    verification_sent: boolean;
    dev_verification_token: string | null;
  }>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      invite_code: inviteCode || undefined,
      phone: phone || undefined,
    }),
  }).then((result) => ({
    email: result.email,
    verificationSent: result.verification_sent,
    devVerificationToken: result.dev_verification_token,
  }));
}

export async function bindPhone(phone: string, password: string): Promise<Me> {
  return request<Me>("/api/v1/auth/bind-phone", {
    method: "POST",
    body: JSON.stringify({ phone, password }),
  });
}

export async function verifyEmail(token: string): Promise<{ verified: boolean; email: string }> {
  return request<{ verified: boolean; email: string }>("/api/v1/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function resendVerification(email: string): Promise<{
  sent: boolean;
  dev_verification_token: string | null;
}> {
  return request<{ sent: boolean; dev_verification_token: string | null }>(
    "/api/v1/auth/resend-verification",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
  );
}

export async function forgotPassword(email: string): Promise<{
  sent: boolean;
  dev_reset_token: string | null;
}> {
  return request<{ sent: boolean; dev_reset_token: string | null }>(
    "/api/v1/auth/forgot-password",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
  );
}

export async function resetPassword(
  token: string,
  password: string,
): Promise<{ reset: boolean }> {
  return request<{ reset: boolean }>("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export async function fetchMe(): Promise<Me> {
  return request<Me>("/api/v1/me");
}

export async function fetchWatchlist(): Promise<ApiEtf[]> {
  return request<ApiEtf[]>("/api/v1/watchlist");
}

export async function addWatchlist(code: string): Promise<{ code: string; saved: boolean }> {
  return request<{ code: string; saved: boolean }>("/api/v1/watchlist", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function removeWatchlist(
  code: string,
): Promise<{ code: string; removed: boolean }> {
  return request<{ code: string; removed: boolean }>(`/api/v1/watchlist/${code}`, {
    method: "DELETE",
  });
}

export type AdminStock = Stock & { status: string };

export type AdminStockPage = {
  items: AdminStock[];
  total: number;
  page: number;
  page_size: number;
};

export async function fetchStockWatchlist(): Promise<Stock[]> {
  return request<Stock[]>("/api/v1/stock-watchlist");
}

export async function addStockWatchlist(
  code: string,
): Promise<{ code: string; saved: boolean }> {
  return request<{ code: string; saved: boolean }>("/api/v1/stock-watchlist", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function removeStockWatchlist(
  code: string,
): Promise<{ code: string; removed: boolean }> {
  return request<{ code: string; removed: boolean }>(
    `/api/v1/stock-watchlist/${code}`,
    { method: "DELETE" },
  );
}

export async function adminListStocks(params: {
  q?: string;
  page?: number;
}): Promise<AdminStockPage> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  search.set("page", String(params.page ?? 1));
  return request<AdminStockPage>(`/api/v1/admin/stocks?${search.toString()}`);
}

export async function adminUpdateStockStatus(
  code: string,
  status: "active" | "excluded",
): Promise<AdminStock> {
  return request<AdminStock>(`/api/v1/admin/stocks/${code}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function adminSyncStock(code: string): Promise<AdminStock> {
  return request<AdminStock>(`/api/v1/admin/stocks/${code}/sync`, {
    method: "POST",
  });
}

export async function redeem(code: string): Promise<{ plan: string; plan_expires_at: string }> {
  return request<{ plan: string; plan_expires_at: string }>("/api/v1/redeem", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function fetchHistory(): Promise<HistoryItem[]> {
  return request<HistoryItem[]>("/api/v1/backtests/history");
}

export async function fetchHistoryDetail(id: number): Promise<BacktestResult> {
  return request<BacktestResult>(`/api/v1/backtests/history/${id}`);
}

export async function adminListCodes(params: {
  status?: string;
  batch_id?: string;
  channel?: string;
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<{
  items: AdminCode[];
  stats: AdminCodeStats;
  total: number;
  page: number;
  page_size: number;
}> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/v1/admin/redeem-codes${suffix}`);
}

export async function adminListBatches(): Promise<BatchSummary[]> {
  return request<BatchSummary[]>("/api/v1/admin/redeem-codes/batches");
}

export async function adminAuditLogs(page = 1): Promise<{
  items: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}> {
  return request(`/api/v1/admin/audit-logs?page=${page}&page_size=10`);
}

export async function adminGenerateCodes(payload: {
  count: number;
  days: number;
  valid_days: number;
  channel: string;
  plan: string;
}): Promise<{ batch_id: string; codes: AdminCode[] }> {
  return request<{ batch_id: string; codes: AdminCode[] }>("/api/v1/admin/redeem-codes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function adminRevokeCode(code: string): Promise<AdminCode> {
  return request<AdminCode>(`/api/v1/admin/redeem-codes/${code}/revoke`, {
    method: "POST",
  });
}

export async function adminExportCsv(filters: {
  status?: string;
  batch_id?: string;
} = {}): Promise<Blob> {
  const token = getToken();
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(`${API_BASE}/api/v1/admin/redeem-codes/export${suffix}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error("导出失败");
  return response.blob();
}

export async function adminCreateOrder(payload: {
  platform: string;
  external_order_id?: string;
  buyer_phone?: string;
  buyer_email?: string;
  amount: number;
  days: number;
  plan: string;
  product: string;
  note?: string;
}): Promise<AdminOrder> {
  return request<AdminOrder>("/api/v1/admin/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function adminListOrders(params: {
  status?: string;
  platform?: string;
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<{
  items: AdminOrder[];
  total: number;
  page: number;
  page_size: number;
  revenue: number;
}> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/v1/admin/orders${suffix}`);
}

export async function adminRefundOrder(orderNo: string): Promise<AdminOrder> {
  return request<AdminOrder>(`/api/v1/admin/orders/${orderNo}/refund`, {
    method: "POST",
  });
}

export async function adminListUsers(params: {
  q?: string;
  plan?: string;
  status?: string;
  role?: string;
  page?: number;
  page_size?: number;
}): Promise<{
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/v1/admin/users${suffix}`);
}

export async function adminUpdateUser(
  id: number,
  payload: { status?: "active" | "banned"; plan?: "free" | "member"; days?: number },
): Promise<AdminUser> {
  return request<AdminUser>(`/api/v1/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function adminGetUserDetail(id: number): Promise<AdminUserDetail> {
  return request<AdminUserDetail>(`/api/v1/admin/users/${id}`);
}

export async function adminUserOrders(
  id: number,
  page = 1,
): Promise<AdminOrderPage> {
  return request<AdminOrderPage>(
    `/api/v1/admin/users/${id}/orders?page=${page}&page_size=10`,
  );
}

export async function adminUserCodes(id: number, page = 1): Promise<AdminCodePage> {
  return request<AdminCodePage>(
    `/api/v1/admin/users/${id}/codes?page=${page}&page_size=10`,
  );
}

export async function adminUserBacktests(
  id: number,
  page = 1,
): Promise<AdminBacktestPage> {
  return request<AdminBacktestPage>(
    `/api/v1/admin/users/${id}/backtests?page=${page}&page_size=10`,
  );
}

export async function adminUserBacktestDetail(
  userId: number,
  runId: number,
): Promise<AdminBacktestDetail> {
  return request<AdminBacktestDetail>(
    `/api/v1/admin/users/${userId}/backtests/${runId}`,
  );
}

export async function adminListInvites(params: {
  status?: string;
  batch_id?: string;
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<{
  items: AdminInvite[];
  stats: AdminInviteStats;
  total: number;
  page: number;
  page_size: number;
}> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/v1/admin/invites${suffix}`);
}

export async function adminListInviteBatches(): Promise<AdminInviteBatch[]> {
  return request<AdminInviteBatch[]>("/api/v1/admin/invites/batches");
}

export async function adminGenerateInvites(payload: {
  count: number;
  max_uses: number;
  valid_days: number;
  note?: string;
  bound_email?: string;
  bound_phone?: string;
}): Promise<{ batch_id: string; codes: AdminInvite[] }> {
  return request<{ batch_id: string; codes: AdminInvite[] }>(
    "/api/v1/admin/invites",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function adminRevokeInvite(code: string): Promise<AdminInvite> {
  return request<AdminInvite>(`/api/v1/admin/invites/${code}/revoke`, {
    method: "POST",
  });
}

export async function adminRevokeInviteBatch(
  batchId: string,
): Promise<{ revoked: number }> {
  return request<{ revoked: number }>(
    `/api/v1/admin/invites/batches/${batchId}/revoke`,
    { method: "POST" },
  );
}

export async function adminInviteUsages(
  code: string,
  page = 1,
): Promise<{
  items: AdminInviteUsage[];
  total: number;
  page: number;
  page_size: number;
}> {
  return request(
    `/api/v1/admin/invites/${code}/usages?page=${page}&page_size=20`,
  );
}

export async function adminExportInvites(filters: {
  status?: string;
  batch_id?: string;
} = {}): Promise<Blob> {
  const token = getToken();
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(`${API_BASE}/api/v1/admin/invites/export${suffix}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error("导出失败");
  return response.blob();
}
