export type Basis = "weighted" | "net" | "dividend" | "unknown";
export type Kind =
  | "snapshot"
  | "buy"
  | "sell"
  | "opening"
  | "adjustment"
  | "reversal"
  | "preference"
  | "rebase"
  | "bonus"
  | "reinvest";
export const basisLabels: Record<Basis, string> = {
  weighted: "加权平均成本",
  net: "摊薄成本（不含分红）",
  dividend: "分红摊薄成本",
  unknown: "口径不确定（参考值）",
};
export const kindLabels: Record<Kind, string> = {
  snapshot: "已有持仓快照",
  rebase: "修正当前持仓",
  buy: "买入",
  sell: "卖出",
  opening: "旧版期初",
  adjustment: "旧版持仓调整",
  reversal: "撤销",
  preference: "展示设置",
  bonus: "送股",
  reinvest: "分红复投",
};
export type StockChoice = {
  code: string;
  name: string;
  is_active: boolean;
  listed_on: string | null;
  currency: string;
  exchange: string;
};
export type Preferences = {
  basis: Basis;
  group: string;
  forecast: "skip" | "12" | "36" | "60" | "custom";
  custom: string | null;
};
export type Cost = {
  total: string | null;
  per_share: string | null;
  status: string;
};
export type Forecast = {
  reason?: string;
  reason_label?: string;
  issues?: string[];
  recorded_total?: string;
  divisor_years?: number;
  coverage_verified?: boolean;
  window: string;
  status: string;
  note: string;
  annual_per_share: string | null;
  annual_amount: string | null;
  from_date: string;
  to_date: string;
  details: {
    included?: boolean;
    exclusion_reason?: string | null;
    event_id: string;
    revision: number;
    report_date: string | null;
    ex_date: string | null;
    cash_per_share: string | null;
    stage: string;
    evidence_status: string;
    source: string;
    source_url: string | null;
  }[];
};
export type Position = {
  code: string;
  name: string;
  quantity: string;
  costs: Record<Exclude<Basis, "unknown">, Cost>;
  reference: string | null;
  preferences: Preferences;
  known_since: string;
  history_status: string;
  date_semantics: string;
  realized_pnl: string | null;
  estimated: boolean;
  market_value: string | null;
  quote: {
    price: string;
    at: string;
    source?: string;
    time_label?: string;
  } | null;
  forecast: Forecast;
  price_yield: string | null;
  price_yield_reason?: string | null;
  price_yield_issues?: string[];
  cost_yield: string | null;
  closed_cycles: {
    cycle_id: string;
    realized_pnl: string | null;
    net: string | null;
    dividend: string | null;
  }[];
};
export type Entry = {
  id: string;
  code: string;
  kind: Kind;
  event_date: string;
  day_order: number;
  quantity: string;
  price: string;
  fees: string;
  total_cost: string;
  active: boolean;
  reverses_id: string | null;
  note: string;
  evidence: string;
  details: {
    basis?: Basis;
    amount?: string;
    input_mode?: "per_share" | "total";
    input_value?: string;
    fees_known?: boolean;
    preferences?: Preferences;
  } | null;
};
export type Holdings = {
  account_version: number;
  consent_required: boolean;
  positions: Position[];
  entries: Entry[];
  known_market_value: string | null;
  missing_quotes: number;
};
export type PositionInput = {
  expected_version: number;
  request_id: string;
  code: string;
  kind: Kind;
  event_date: string;
  quantity: string;
  cost: string;
  input_mode: "per_share" | "total";
  basis: Basis;
  fees: string | null;
  preferences: Preferences;
  day_order: number | null;
  note: string;
  evidence: string;
  reverses_id: string | null;
};
export type Preview = {
  preview_token: string;
  expires_in: number;
  summary: {
    forecast?: Forecast;
    stock: StockChoice;
    kind: Kind;
    event_date: string;
    day_order: number;
    quantity: string;
    input_value: string;
    input_mode: string;
    basis: Basis;
    amount: string | null;
    fees: string | null;
    fees_known: boolean;
    resulting_position: Pick<Position, "quantity" | "costs"> | null;
    warning: string;
    date_semantics: string;
  };
};
export const defaultPreferences = (): Preferences => ({
  basis: "weighted",
  group: "",
  forecast: "skip",
  custom: null,
});
export const shanghaiToday = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export const amount = (value: string | null | undefined) =>
  value == null ? "—" : value.replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
// UI arithmetic only for explanatory amounts. Financial acceptance/replay stays on the server.
export function inputTotal(
  quantity: string,
  price: string,
  fees = "0",
): string | null {
  const scale = 1000000n;
  const parse = (s: string) => {
    if (!/^-?\d{1,12}(\.\d{1,6})?$/.test(s)) throw new Error();
    const [a, b = ""] = s.replace("-", "").split(".");
    return (
      (BigInt(a) * scale + BigInt(b.padEnd(6, "0"))) *
      (s.startsWith("-") ? -1n : 1n)
    );
  };
  try {
    const raw = parse(quantity) * parse(price);
    const sign = raw < 0n ? -1n : 1n;
    const total =
      sign * ((raw * sign + scale / 2n) / scale) + parse(fees || "0");
    const abs = total < 0n ? -total : total;
    return `${total < 0n ? "-" : ""}${abs / scale}.${String(abs % scale).padStart(6, "0")}`;
  } catch {
    return null;
  }
}
