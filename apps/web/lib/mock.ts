export type EtfCategory = "红利" | "现金流" | "跨境" | "宽基" | "行业";

export type Etf = {
  code: string;
  name: string;
  category: EtfCategory;
  price: number;
  change: number;
  aum: number | null;
  dividendYield: number | null;
  pePercentile: number | null;
  ma20?: number | null;
  maxDrawdown?: number | null;
  turnover?: number | null;
};

export type IndexQuote = {
  name: string;
  value: number;
  change: number;
};

export type Strategy = {
  slug: string;
  name: string;
  tag: string;
  summary: string;
  totalReturn: number;
  annual: number;
  maxDrawdown: number;
  sharpe: number;
  trades: number;
  curve: number[];
};

export const indices: IndexQuote[] = [
  { name: "上证指数", value: 3342.12, change: 0.62 },
  { name: "沪深 300", value: 4018.55, change: 0.48 },
  { name: "创业板指", value: 2311.09, change: -0.35 },
  { name: "恒生科技", value: 5210.33, change: 1.24 },
  { name: "标普 500", value: 5670.2, change: -0.12 },
];

export const etfs: Etf[] = [
  { code: "512890", name: "中证红利低波ETF", category: "红利", price: 1.218, change: 0.41, aum: 189.4, dividendYield: 4.8, pePercentile: 28 },
  { code: "515450", name: "红利低波50ETF", category: "红利", price: 1.462, change: 0.28, aum: 76.2, dividendYield: 4.6, pePercentile: 31 },
  { code: "515100", name: "红利低波100ETF", category: "红利", price: 1.352, change: 0.35, aum: 42.8, dividendYield: 4.5, pePercentile: 33 },
  { code: "515080", name: "中证红利ETF", category: "红利", price: 1.531, change: 0.19, aum: 58.6, dividendYield: 5.1, pePercentile: 25 },
  { code: "561580", name: "央企红利ETF", category: "红利", price: 1.104, change: 0.55, aum: 21.3, dividendYield: 4.9, pePercentile: 22 },
  { code: "510880", name: "上证红利ETF", category: "红利", price: 3.276, change: 0.24, aum: 158.7, dividendYield: 5.3, pePercentile: 27 },
  { code: "159201", name: "自由现金流ETF", category: "现金流", price: 1.082, change: 0.66, aum: 33.5, dividendYield: 3.2, pePercentile: 35 },
  { code: "560120", name: "中证500现金流ETF", category: "现金流", price: 1.014, change: 0.72, aum: 12.6, dividendYield: 2.9, pePercentile: 41 },
  { code: "159941", name: "纳指100ETF", category: "跨境", price: 5.842, change: 1.12, aum: 245.1, dividendYield: 0.6, pePercentile: 88 },
  { code: "513500", name: "标普500ETF", category: "跨境", price: 2.318, change: 0.87, aum: 178.9, dividendYield: 1.2, pePercentile: 82 },
  { code: "513880", name: "日经225ETF", category: "跨境", price: 1.764, change: -0.42, aum: 18.4, dividendYield: 1.0, pePercentile: 74 },
  { code: "513050", name: "中概互联网ETF", category: "跨境", price: 1.286, change: 1.85, aum: 312.6, dividendYield: null, pePercentile: 46 },
  { code: "513180", name: "恒生科技ETF", category: "跨境", price: 0.742, change: 2.1, aum: 289.3, dividendYield: null, pePercentile: 52 },
  { code: "513330", name: "恒生互联网ETF", category: "跨境", price: 0.518, change: 1.96, aum: 201.4, dividendYield: null, pePercentile: 49 },
  { code: "510300", name: "沪深300ETF", category: "宽基", price: 4.212, change: 0.48, aum: 1280.5, dividendYield: 2.1, pePercentile: 38 },
  { code: "510500", name: "中证500ETF", category: "宽基", price: 6.184, change: 0.75, aum: 486.2, dividendYield: 1.7, pePercentile: 44 },
  { code: "512100", name: "中证1000ETF", category: "宽基", price: 2.436, change: 1.02, aum: 198.7, dividendYield: 1.2, pePercentile: 47 },
  { code: "563360", name: "中证A500ETF", category: "宽基", price: 1.128, change: 0.53, aum: 156.4, dividendYield: 2.0, pePercentile: 40 },
  { code: "512480", name: "半导体ETF", category: "行业", price: 1.286, change: 2.35, aum: 208.9, dividendYield: 0.4, pePercentile: 71 },
  { code: "515030", name: "新能源车ETF", category: "行业", price: 1.174, change: -0.86, aum: 96.3, dividendYield: 0.8, pePercentile: 58 },
];

export const categories: EtfCategory[] = ["红利", "现金流", "跨境", "宽基", "行业"];

export const sectors = [
  { name: "电子", change: 2.4 },
  { name: "计算机", change: 1.8 },
  { name: "通信", change: 1.2 },
  { name: "汽车", change: 0.6 },
  { name: "有色金属", change: 0.9 },
  { name: "国防军工", change: 1.5 },
  { name: "食品饮料", change: -0.4 },
  { name: "银行", change: -0.8 },
  { name: "医药生物", change: -1.1 },
  { name: "电力设备", change: -1.6 },
  { name: "房地产", change: -2.2 },
  { name: "煤炭", change: -0.3 },
];

export const strategies: Strategy[] = [
  {
    slug: "buy-and-hold",
    name: "买入持有",
    tag: "基准",
    summary: "首个交易日全仓买入，持有不动。用来回答：择时到底有没有比一直拿着更好。",
    totalReturn: 62.4,
    annual: 8.1,
    maxDrawdown: -21.6,
    sharpe: 0.62,
    trades: 1,
    curve: [100, 103, 99, 106, 111, 108, 116, 121, 118, 125, 130, 127, 134, 139, 136, 143, 148, 145, 151, 156, 152, 158, 162, 162.4],
  },
  {
    slug: "monthly-dca",
    name: "每月定投",
    tag: "定投",
    summary: "每月首个交易日固定金额买入，把成本摊开，观察分批投入与一次性买入的差别。",
    totalReturn: 28.7,
    annual: 5.2,
    maxDrawdown: -14.3,
    sharpe: 0.51,
    trades: 36,
    curve: [100, 101, 100, 103, 105, 104, 107, 109, 108, 111, 113, 112, 115, 117, 116, 119, 121, 120, 123, 125, 124, 126, 128, 128.7],
  },
  {
    slug: "dual-ma",
    name: "双均线",
    tag: "趋势",
    summary: "快线上穿慢线买入，下穿卖出。全仓进出，用趋势过滤震荡期的反复打脸。",
    totalReturn: 41.2,
    annual: 7.0,
    maxDrawdown: -12.8,
    sharpe: 0.74,
    trades: 18,
    curve: [100, 102, 101, 105, 108, 106, 110, 112, 111, 115, 118, 116, 119, 122, 120, 124, 127, 125, 128, 131, 130, 134, 137, 141.2],
  },
  {
    slug: "rsi",
    name: "RSI 超买超卖",
    tag: "摆动",
    summary: "RSI 低于超卖线买入，高于超买线卖出，中间区间保持仓位。",
    totalReturn: 36.4,
    annual: 6.4,
    maxDrawdown: -13.5,
    sharpe: 0.68,
    trades: 24,
    curve: [100, 101, 104, 102, 106, 110, 108, 112, 109, 114, 118, 115, 119, 123, 120, 124, 128, 125, 129, 132, 130, 133, 135, 136.4],
  },
  {
    slug: "bollinger",
    name: "布林带",
    tag: "摆动",
    summary: "收盘跌破下轨买入，回到中轨上方卖出；震荡市信号更多。",
    totalReturn: 44.1,
    annual: 7.3,
    maxDrawdown: -14.9,
    sharpe: 0.72,
    trades: 22,
    curve: [100, 103, 101, 105, 109, 107, 111, 114, 112, 116, 120, 118, 122, 126, 124, 128, 132, 130, 134, 138, 136, 140, 143, 144.1],
  },
  {
    slug: "macd",
    name: "MACD",
    tag: "趋势",
    summary: "DIF 上穿 DEA 买入，下穿卖出；用快慢线过滤短期噪音。",
    totalReturn: 39.6,
    annual: 6.8,
    maxDrawdown: -15.7,
    sharpe: 0.66,
    trades: 30,
    curve: [100, 102, 100, 104, 108, 105, 109, 112, 110, 114, 117, 115, 119, 122, 120, 124, 127, 125, 129, 133, 131, 135, 138, 139.6],
  },
  {
    slug: "deviation",
    name: "偏离度调仓",
    tag: "仓位",
    summary: "价格低于均线越多，目标仓位越高；只买卖差额部分，允许长期半仓。",
    totalReturn: 53.8,
    annual: 8.8,
    maxDrawdown: -15.1,
    sharpe: 0.81,
    trades: 64,
    curve: [100, 101, 103, 102, 106, 109, 108, 112, 115, 113, 117, 120, 119, 123, 126, 124, 128, 131, 130, 134, 137, 136, 140, 153.8],
  },
  {
    slug: "grid",
    name: "滚动网格",
    tag: "网格",
    summary: "在滚动高低点之间等分网格，价格越低仓位越高，越高越减。",
    totalReturn: 31.5,
    annual: 5.6,
    maxDrawdown: -11.2,
    sharpe: 0.7,
    trades: 48,
    curve: [100, 102, 101, 104, 107, 106, 109, 111, 110, 113, 116, 115, 118, 121, 120, 123, 126, 125, 128, 130, 129, 131, 132, 131.5],
  },
];

export function getEtf(code: string): Etf | undefined {
  return etfs.find((item) => item.code === code);
}

export function getStrategy(slug: string): Strategy | undefined {
  return strategies.find((item) => item.slug === slug);
}
