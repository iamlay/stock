import Link from "next/link";

const SECTIONS = [
  { href: "/stocks", label: "高股息", key: "dividend" },
  { href: "/stocks/grid", label: "网格", key: "grid" },
  { href: "/stocks/bollinger", label: "布林", key: "bollinger" },
  { href: "/stocks/financial", label: "财务", key: "financial" },
] as const;

export function StockSectionTabs({ active }: { active: string }) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-line pb-3">
      {SECTIONS.map((item) => (
        <Link
          key={item.key}
          href={item.href}
          className={`rounded-sm px-3 py-1.5 text-sm transition-colors ${
            active === item.key
              ? "bg-ink text-paper"
              : "text-ink-soft hover:bg-black/[0.04]"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
}
