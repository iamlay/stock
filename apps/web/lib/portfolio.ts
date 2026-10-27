import { getToken } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type PortfolioPolicy = {
  policy: { version: string; title: string; sections: string[]; privacy_path: string; scope: string };
  sha256: string;
};
export type PortfolioAccount = {
  id: string; name: string; currency: "CNY"; is_archived: boolean; version: number;
  created_at: string; updated_at: string;
};
export type PortfolioList = { items: PortfolioAccount[]; create_enabled: boolean; account_limit: number };

export class PortfolioRequestError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

export async function portfolioRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}/api/v1/portfolio${path}`, {
    ...init, cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    let code = "request_failed";
    let message = "暂时无法完成操作，请稍后重试。";
    try {
      const data = await response.json();
      if (data.detail && typeof data.detail === "object") {
        if (typeof data.detail.code === "string") code = data.detail.code;
        if (typeof data.detail.message === "string") message = data.detail.message;
      } else if (response.status === 403) message = "请先验证邮箱，或等待私人账本开放。";
    } catch { /* Do not display arbitrary server bodies containing submitted private fields. */ }
    if (response.status === 401) message = "登录已过期，请重新登录。";
    throw new PortfolioRequestError(response.status, code, message);
  }
  return await response.json() as T;
}

export function validPortfolioPolicy(value: unknown): value is PortfolioPolicy {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<PortfolioPolicy>;
  return typeof item.sha256 === "string" && /^[a-f0-9]{64}$/.test(item.sha256) &&
    typeof item.policy?.version === "string" && item.policy.version.length > 0 &&
    item.policy.scope === "private_account_metadata" &&
    typeof item.policy.title === "string" && item.policy.privacy_path === "/legal/privacy#portfolio-data" &&
    Array.isArray(item.policy.sections) && item.policy.sections.length > 0 &&
    item.policy.sections.every((section) => typeof section === "string");
}
