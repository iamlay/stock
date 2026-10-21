type HeatItem = {
  name: string;
  change: number;
  count: number;
};

export function CategoryHeatChart({
  data,
  note = "每类 ETF 等权，非申万行业",
}: {
  data: HeatItem[];
  note?: string;
}) {
  const sorted = [...data].sort((a, b) => b.change - a.change);
  const maxAbs = Math.max(...sorted.map((item) => Math.abs(item.change)), 0.1);

  return (
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between text-[11px] text-muted">
        <span>分类等权涨跌幅</span>
        <span>红涨绿跌</span>
      </div>
      <div className="space-y-2">
        {sorted.map((item) => {
          const width = Math.max(2, (Math.abs(item.change) / maxAbs) * 50);
          const positive = item.change >= 0;
          return (
            <div
              key={item.name}
              className="grid grid-cols-[64px_1fr_58px] items-center gap-2"
              aria-label={`${item.name} ${item.change.toFixed(2)}%`}
            >
              <div className="flex items-baseline justify-between gap-1 text-xs">
                <span className="text-ink-soft">{item.name}</span>
              </div>
              <div className="relative h-5 overflow-hidden rounded-sm bg-[#f4f1e9]">
                <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
                <div
                  className={`absolute inset-y-0.5 rounded-sm ${
                    positive ? "bg-loss/70" : "bg-jade/70"
                  }`}
                  style={{
                    left: positive ? "50%" : `${50 - width}%`,
                    width: `${width}%`,
                  }}
                />
              </div>
              <div
                className={`tnum text-right text-xs font-medium ${
                  positive ? "text-loss" : "text-jade"
                }`}
              >
                {item.change > 0 ? "+" : ""}
                {item.change.toFixed(2)}%
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center justify-between text-[11px] text-muted">
        <span>{note}</span>
        <span>{sorted.reduce((sum, item) => sum + item.count, 0)} 只样本</span>
      </div>
    </div>
  );
}
