export function fmtPct(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function fmtNumber(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function trendClass(value: number): string {
  if (value > 0) return "text-loss";
  if (value < 0) return "text-jade";
  return "text-muted";
}

export function trendBg(value: number): string {
  const abs = Math.min(Math.abs(value) / 3, 1);
  if (value > 0) return `rgba(180, 35, 24, ${0.08 + abs * 0.22})`;
  if (value < 0) return `rgba(11, 122, 92, ${0.08 + abs * 0.22})`;
  return "rgba(109, 118, 129, 0.08)";
}
