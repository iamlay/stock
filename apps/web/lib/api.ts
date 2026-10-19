import type { Etf, EtfCategory } from "@/lib/mock";

const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export type ApiEtf = {
  code: string;
  name: string;
  category: string;
  tracked_index: string | null;
  trade_date: string | null;
  price: number;
  change_pct: number;
  ma5: number | null;
  ma20: number | null;
  ma60: number | null;
  volatility_20d: number | null;
  max_drawdown_1y: number | null;
  high_52w: number | null;
  low_52w: number | null;
  aum: number | null;
  shares: number | null;
  turnover: number | null;
};

export type ApiEtfDetail = ApiEtf & {
  fee_rate: number | null;
  return_1m: number | null;
  return_3m: number | null;
  return_1y: number | null;
  bars: { date: string; close: number }[];
};

export type ApiOverview = {
  trade_date: string | null;
  demo: boolean;
  etf_count: number;
  avg_change_pct: number | null;
  advancing: number;
  declining: number;
  turnover_billion: number | null;
  top_gainers: { code: string; name: string; change_pct: number }[];
  top_losers: { code: string; name: string; change_pct: number }[];
  note: string;
};

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(4000),
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function toEtf(item: ApiEtf): Etf {
  return {
    code: item.code,
    name: item.name,
    category: item.category as EtfCategory,
    price: item.price,
    change: item.change_pct,
    aum: item.aum,
    dividendYield: null,
    pePercentile: null,
    ma20: item.ma20,
    maxDrawdown: item.max_drawdown_1y,
    turnover: item.turnover,
  };
}

export async function fetchEtfs(): Promise<ApiEtf[] | null> {
  return fetchJson<ApiEtf[]>("/api/v1/etfs");
}

export async function fetchEtf(code: string): Promise<ApiEtfDetail | null> {
  return fetchJson<ApiEtfDetail>(`/api/v1/etfs/${code}`);
}

export async function fetchOverview(): Promise<ApiOverview | null> {
  return fetchJson<ApiOverview>("/api/v1/market/overview");
}
