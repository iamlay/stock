import type { BacktestResult } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "stocklab.token";

export type Me = {
  id: number;
  phone: string;
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

export async function fetchMe(): Promise<Me> {
  return request<Me>("/api/v1/me");
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

export async function adminListCodes(status?: string): Promise<{
  items: AdminCode[];
  stats: AdminCodeStats;
}> {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<{ items: AdminCode[]; stats: AdminCodeStats }>(
    `/api/v1/admin/redeem-codes${suffix}`,
  );
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

export async function adminExportCsv(status?: string): Promise<Blob> {
  const token = getToken();
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await fetch(`${API_BASE}/api/v1/admin/redeem-codes/export${suffix}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error("导出失败");
  return response.blob();
}
