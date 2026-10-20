import { indices } from "@/lib/mock";
import { fmtPct, trendClass } from "@/lib/format";

type TickerItem = { name: string; value: number; change: number };

export function TickerStrip({ items }: { items?: TickerItem[] }) {
  const data = items && items.length > 0 ? items : indices;
  return (
    <div className="border-b border-line bg-surface/70">
      <div className="mx-auto flex max-w-6xl gap-8 overflow-x-auto px-6 py-2.5 text-xs">
        {data.map((item) => (
          <div key={item.name} className="flex shrink-0 items-baseline gap-2">
            <span className="text-muted">{item.name}</span>
            <span className="tnum font-medium text-ink">{item.value.toLocaleString("zh-CN")}</span>
            <span className={`tnum ${trendClass(item.change)}`}>{fmtPct(item.change)}</span>
          </div>
        ))}
        <span className="ml-auto hidden shrink-0 text-muted lg:block">日线数据 · 非实时行情</span>
      </div>
    </div>
  );
}
