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
