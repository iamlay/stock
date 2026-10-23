import type { StockBand } from "@/lib/stocks";

export type BollingerResult = {
  daily: StockBand | null;
  weekly: StockBand | null;
  monthly: StockBand | null;
  rating: string;
};

function isoWeek(date: Date): { year: number; week: number } {
  const target = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((target.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return { year: target.getUTCFullYear(), week };
}

function band(closes: number[]): StockBand | null {
  const period = 20;
  if (closes.length < period) return null;

  const window = closes.slice(-period);
  const mid = window.reduce((sum, value) => sum + value, 0) / period;
  const variance =
    window.reduce((sum, value) => sum + (value - mid) ** 2, 0) / period;
  const std = Math.sqrt(variance);
  const upper = mid + 2 * std;
  const lower = mid - 2 * std;
  const close = closes[closes.length - 1];

  let position = "中下";
  if (close >= upper) position = "上轨上方";
  else if (close >= mid) position = "中上";
  else if (close < lower) position = "下轨下方";

  const width = upper - lower;
  return {
    position,
    close: Number(close.toFixed(3)),
    mid: Number(mid.toFixed(3)),
    upper: Number(upper.toFixed(3)),
    lower: Number(lower.toFixed(3)),
    percent_b: width > 0 ? Number((((close - lower) / width) * 100).toFixed(1)) : 50,
    periods: period,
  };
}

function periodCloses(
  bars: { date: string; close: number }[],
  kind: "week" | "month",
): number[] {
  const grouped = new Map<string, number>();
  for (const bar of bars) {
    const date = new Date(`${bar.date}T00:00:00Z`);
    const key =
      kind === "month"
        ? `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`
        : (() => {
            const iso = isoWeek(date);
            return `${iso.year}-W${String(iso.week).padStart(2, "0")}`;
          })();
    grouped.set(key, bar.close);
  }
  return Array.from(grouped.keys())
    .sort()
    .map((key) => grouped.get(key)!);
}

function rating(
  daily: StockBand | null,
  weekly: StockBand | null,
  monthly: StockBand | null,
): string {
  if (!daily) return "数据不足";
  const weakDaily = ["下轨下方", "中下"].includes(daily.position);
  const weakWeekly = weekly ? ["下轨下方", "中下"].includes(weekly.position) : true;
  const hotDaily = ["上轨上方", "中上"].includes(daily.position);
  const hotWeekly = weekly ? ["上轨上方", "中上"].includes(weekly.position) : true;

  if (weakDaily && weakWeekly) return "回踩";
  if (hotDaily && hotWeekly) return "偏热";
  if (monthly?.position === "上轨上方") return "高位";
  return "观望";
}

export function computeBollinger(
  bars: { date: string; close: number }[],
): BollingerResult {
  const ordered = [...bars].sort((a, b) => a.date.localeCompare(b.date));
  const daily = band(ordered.map((bar) => bar.close));
  const weekly = band(periodCloses(ordered, "week"));
  const monthly = band(periodCloses(ordered, "month"));
  return { daily, weekly, monthly, rating: rating(daily, weekly, monthly) };
}
