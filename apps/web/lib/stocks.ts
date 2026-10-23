const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
const PUBLIC_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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
  sustainability: string | null;
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
  is_one_off: boolean;
};

export type StockDetail = Stock & {
  dividends: StockDividend[];
  bars: { date: string; close: number }[];
};

export type StockBand = {
  position: string;
  close: number;
  mid: number;
  upper: number;
  lower: number;
  percent_b: number;
  periods: number;
};

export type StockBollinger = Stock & {
  daily: StockBand | null;
  weekly: StockBand | null;
  monthly: StockBand | null;
  rating: string;
};

export type StockBollingerList = {
  items: StockBollinger[];
  total: number;
  page: number;
  page_size: number;
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

export async function fetchStockBollinger(
  params: { q?: string; industry?: string; page?: number; page_size?: number } = {},
): Promise<StockBollingerList | null> {
  try {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === "") continue;
      search.set(key, String(value));
    }
    const response = await fetch(
      `${API_BASE}/api/v1/stocks/bollinger?${search.toString()}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
      },
    );
    if (!response.ok) return null;
    return (await response.json()) as StockBollingerList;
  } catch {
    return null;
  }
}

export async function searchStocks(query: string): Promise<Stock[]> {
  const text = query.trim();
  if (!text) return [];
  try {
    const response = await fetch(
      `${PUBLIC_API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(text)}`,
      { signal: AbortSignal.timeout(5000) },
    );
    if (!response.ok) return [];
    return (await response.json()) as Stock[];
  } catch {
    return [];
  }
}
