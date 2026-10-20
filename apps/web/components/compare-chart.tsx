import type { CompareItem } from "@/lib/api";

const COLORS = ["#0b7a5c", "#c2410c", "#1d4ed8", "#a16207", "#7c3aed"];

export function CompareChart({ items }: { items: CompareItem[] }) {
  const width = 860;
  const height = 300;
  const padX = 44;
  const padY = 24;
  const values = items.flatMap((item) => item.series.map((point) => point.value));
  if (values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = items[0].series.length;

  function x(index: number): number {
    return padX + (index / Math.max(1, points - 1)) * (width - padX * 2);
  }

  function y(value: number): number {
    return height - padY - ((value - min) / span) * (height - padY * 2);
  }

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="ETF 归一化对比">
        <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} stroke="#ddd8cc" />
        <line x1={padX} y1={padY} x2={padX} y2={height - padY} stroke="#ddd8cc" />
        <text x={padX - 8} y={padY + 4} textAnchor="end" fontSize="11" fill="#7a7568">
          {max.toFixed(1)}
        </text>
        <text x={padX - 8} y={height - padY} textAnchor="end" fontSize="11" fill="#7a7568">
          {min.toFixed(1)}
        </text>
        {items.map((item, itemIndex) => (
          <polyline
            key={item.code}
            fill="none"
            stroke={COLORS[itemIndex % COLORS.length]}
            strokeWidth={2}
            points={item.series
              .map((point, index) => `${x(index).toFixed(1)},${y(point.value).toFixed(1)}`)
              .join(" ")}
          />
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted">
        {items.map((item, index) => (
          <span key={item.code} className="inline-flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: COLORS[index % COLORS.length] }}
            />
            {item.name}（{item.code}）
          </span>
        ))}
      </div>
    </div>
  );
}
