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
  pe: number | null;
  pb: number | null;
  pe_percentile: number | null;
  dividend_yield: number | null;
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

export type BacktestMetrics = {
  total_return: number;
  annualized_return: number;
  max_drawdown: number;
  volatility: number;
  sharpe: number;
  exposure: number;
  trades: number;
  win_rate: number | null;
  benchmark_return: number;
  final_equity: number;
};

export type BacktestTrade = {
  date: string;
  side: string;
  price: number;
  shares: number;
  amount: number;
  fee: number;
  reason: string;
  realized_pnl: number | null;
};

export type BacktestResult = {
  code: string;
  strategy: string;
  params: Record<string, number>;
  start: string | null;
  end: string | null;
  metrics: BacktestMetrics;
  equity: { date: string; equity: number; benchmark: number; shares: number }[];
  trades: BacktestTrade[];
  warnings: string[];
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
    dividendYield: item.dividend_yield,
    pePercentile: item.pe_percentile,
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

export async function runBacktest(body: {
  code: string;
  strategy: string;
  start?: string;
  end?: string;
  params?: Record<string, number>;
}): Promise<BacktestResult | null> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/backtests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return null;
    return (await response.json()) as BacktestResult;
  } catch {
    return null;
  }
}
