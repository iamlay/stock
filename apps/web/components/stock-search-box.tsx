"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { searchStocks, type Stock } from "@/lib/stocks";

export function StockSearchBox() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Stock[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.trim().length === 0) {
      setItems([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    const timer = window.setTimeout(() => {
      searchStocks(query)
        .then((result) => {
          setItems(result);
          setOpen(true);
        })
        .finally(() => setLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (wrapper.current && !wrapper.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function submit() {
    if (!query.trim()) return;
    setOpen(false);
    router.push(`/stocks?q=${encodeURIComponent(query.trim())}`);
  }

  return (
    <div ref={wrapper} className="relative w-full max-w-sm">
      <div className="flex items-center gap-2 rounded-sm border border-line bg-surface px-3 py-2">
        <span className="text-xs text-muted">搜索</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => items.length > 0 && setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submit();
            if (event.key === "Escape") setOpen(false);
          }}
          placeholder="代码或名称，回车筛选"
          className="w-full bg-transparent text-sm text-ink outline-none"
        />
        {loading ? <span className="text-[10px] text-muted">…</span> : null}
      </div>
      {open && items.length > 0 ? (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-sm border border-line bg-surface shadow-lg">
          {items.map((item) => (
            <button
              key={item.code}
              type="button"
              onClick={() => {
                setOpen(false);
                router.push(`/stocks/${item.code}`);
              }}
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-jade-soft"
            >
              <span>
                <span className="tnum mr-2 text-xs text-muted">{item.code}</span>
                {item.name}
              </span>
              <span className="tnum text-xs text-jade-deep">
                {item.dividend_yield_ttm == null
                  ? "—"
                  : `${item.dividend_yield_ttm.toFixed(2)}%`}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
