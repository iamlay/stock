import type { Basis } from "./portfolio-positions";

export const shortBasis: Record<Basis, string> = {
  weighted: "加权成本",
  net: "摊薄成本",
  dividend: "分红摊薄",
  unknown: "成本口径待确认",
};
// Formatting only. All financial values and yields come from the server.
export function displayNumber(
  value: string | null | undefined,
  digits = 2,
  compact = false,
): string {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("zh-CN", {
    notation:
      compact && Math.abs(Number(value)) >= 10000 ? "compact" : "standard",
    minimumFractionDigits: compact ? 0 : digits,
    maximumFractionDigits: compact ? 2 : digits,
  }).format(Number(value));
}
export const displayMoney = (
  value: string | null | undefined,
  compact = false,
) => (value == null ? "—" : `¥${displayNumber(value, 2, compact)}`);
export const displayPercent = (value: string | null | undefined) =>
  value == null ? "—" : `${displayNumber(value, 2)}%`;

export const displayQuantity = (value: string) =>
  new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 6 }).format(
    Number(value),
  );
