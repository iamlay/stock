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
  financials: StockFinancialReport[];
};

export type StockFinancialReport = {
  report_date: string;
  period: string;
  revenue: number | null;
  net_profit: number | null;
  revenue_yoy: number | null;
  net_profit_yoy: number | null;
  roe: number | null;
  operating_cash_flow_per_share: number | null;
  operating_cash_flow: number | null;
  gross_margin: number | null;
  net_margin: number | null;
  total_assets: number | null;
  total_liabilities: number | null;
  debt_asset_ratio: number | null;
  roa: number | null;
  disclosure_date: string | null;
};

export type AnnualFinancial = {
  year: number;
  net_profit: number | null;
  net_profit_yoy: number | null;
};

export type StockFinancialSummary = Stock & {
  annuals: AnnualFinancial[];
  latest_period: string | null;
  latest_report_date: string | null;
  latest_net_profit: number | null;
  latest_net_profit_yoy: number | null;
  latest_revenue_yoy: number | null;
  latest_roe: number | null;
  latest_operating_cash_flow_per_share: number | null;
  latest_operating_cash_flow: number | null;
  latest_gross_margin: number | null;
  latest_net_margin: number | null;
  latest_roa: number | null;
  latest_debt_asset_ratio: number | null;
  disclosure_date: string | null;
};

export type StockFinancialList = {
  items: StockFinancialSummary[];
  total: number;
  page: number;
  page_size: number;
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

export async function fetchStock(
  code: string,
  token?: string | null,
): Promise<StockDetail | null> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/stocks/${code}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) return null;
    return (await response.json()) as StockDetail;
  } catch {
    return null;
  }
}

export async function fetchStockBollinger(
  params: { q?: string; industry?: string; page?: number; page_size?: number } = {},
  token?: string | null,
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
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      },
    );
    if (!response.ok) return null;
    return (await response.json()) as StockBollingerList;
  } catch {
    return null;
  }
}

export async function fetchStockFinancials(
  params: { q?: string; industry?: string; page?: number; page_size?: number } = {},
  token?: string | null,
): Promise<StockFinancialList | null> {
  try {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === "") continue;
      search.set(key, String(value));
    }
    const response = await fetch(
      `${API_BASE}/api/v1/stocks/financials?${search.toString()}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      },
    );
    if (!response.ok) return null;
    return (await response.json()) as StockFinancialList;
  } catch {
    return null;
  }
}

export async function searchStocks(query: string): Promise<Stock[]> {  const text = query.trim();
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
