type EquityCurveProps = {
  points: number[];
  id: string;
  height?: number;
  stroke?: string;
  fill?: string;
  className?: string;
};

export function EquityCurve({
  points,
  id,
  height = 180,
  stroke = "#0b7a5c",
  fill = "rgba(11, 122, 92, 0.10)",
  className,
}: EquityCurveProps) {
  const width = 560;
  const pad = 10;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = (width - pad * 2) / Math.max(points.length - 1, 1);

  const coords = points.map((point, index) => {
    const x = pad + index * step;
    const y = pad + (height - pad * 2) * (1 - (point - min) / span);
    return [x, y] as const;
  });

  const line = coords
    .map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${coords[coords.length - 1][0].toFixed(1)},${height - pad} L${coords[0][0].toFixed(1)},${height - pad} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={className ?? "block h-auto w-full max-w-full"}
      role="img"
      aria-label="策略净值曲线（示例数据）"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fill} />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((ratio) => (
        <line
          key={ratio}
          x1={pad}
          x2={width - pad}
          y1={pad + (height - pad * 2) * ratio}
          y2={pad + (height - pad * 2) * ratio}
          stroke="#e2dfd5"
          strokeDasharray="2 4"
        />
      ))}
      <path d={area} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" />
    </svg>
  );
}
