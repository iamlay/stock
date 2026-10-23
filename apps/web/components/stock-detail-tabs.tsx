import Link from "next/link";

const TABS = [
  { key: "overview", label: "概览" },
  { key: "dividend", label: "分红" },
  { key: "grid", label: "网格" },
  { key: "bollinger", label: "布林" },
  { key: "financial", label: "财务" },
] as const;

export function StockDetailTabs({
  code,
  active,
}: {
  code: string;
  active: string;
}) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-line pb-3">
      {TABS.map((tab) => (
        <Link
          key={tab.key}
          href={`/stocks/${code}?tab=${tab.key}`}
          className={`rounded-sm px-3 py-1.5 text-sm transition-colors ${
            active === tab.key
              ? "bg-ink text-paper"
              : "text-ink-soft hover:bg-black/[0.04]"
          }`}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
