const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export type Stock = {
  code: string;
  name: string;
  industry: string | null;
  industry_path: string | null;
  market: string | null;
  is_st: boolean;
  price: number | null;
  change_pct: number | null;
  market_cap: number | null;
  pe_ttm: number | null;
  pb: number | null;
  dividend_yield_ttm: number | null;
  dividend_yield_fy: number | null;
  last_ex_date: string | null;
  updated_at: string | null;
};

export type StockList = {
  items: Stock[];
  total: number;
  page: number;
  page_size: number;
  sort: string;
  order: string;
};

export type StockDividend = {
  ex_date: string;
  fiscal_year: number;
  cash_per_share: number;
  plan: string;
  is_special: boolean;
};

export type StockDetail = Stock & {
  dividends: StockDividend[];
};

export type StockQuery = {
  sort?: string;
  order?: "asc" | "desc";
  q?: string;
  industry?: string;
  min_yield?: number;
  include_st?: boolean;
  page?: number;
  page_size?: number;
};

function queryString(params: StockQuery): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "" || value === false) continue;
    search.set(key, String(value));
  }
  return search.toString();
}

export async function fetchStocks(params: StockQuery = {}): Promise<StockList | null> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/stocks?${queryString(params)}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return null;
    return (await response.json()) as StockList;
  } catch {
    return null;
  }
}

export async function fetchStock(code: string): Promise<StockDetail | null> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/stocks/${code}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return null;
    return (await response.json()) as StockDetail;
  } catch {
    return null;
  }
}
