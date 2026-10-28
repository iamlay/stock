"use client";

import { useEffect, useRef, useState } from "react";
import { portfolioRequest } from "@/lib/portfolio";
import type { StockChoice } from "@/lib/portfolio-positions";

export function PortfolioStockPicker({
  accountId,
  selected,
  onSelect,
  disabled,
  onError,
}: {
  accountId: string;
  selected: StockChoice | null;
  onSelect: (stock: StockChoice | null) => void;
  disabled: boolean;
  onError: (err: unknown) => void;
}) {
  const [query, setQuery] = useState(selected?.name ?? "");
  const [items, setItems] = useState<StockChoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [highlight, setHighlight] = useState(0);
  const generation = useRef(0);
  const errorHandler = useRef(onError);
  errorHandler.current = onError;
  useEffect(() => {
    const seq = ++generation.current;
    const controller = new AbortController();
    if (selected || !query.trim()) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setFailed(false);
    const timer = window.setTimeout(() => {
      void portfolioRequest<{ items: StockChoice[] }>(
        `/accounts/${accountId}/stock-search`,
        {
          method: "POST",
          body: JSON.stringify({ query: query.trim() }),
          signal: controller.signal,
        },
      )
        .then((data) => {
          if (generation.current === seq) {
            setItems(data.items);
            setHighlight(0);
          }
        })
        .catch((err) => {
          if (generation.current === seq && !controller.signal.aborted) {
            setFailed(true);
            errorHandler.current(err);
          }
        })
        .finally(() => {
          if (generation.current === seq) setLoading(false);
        });
    }, 250);
    return () => {
      ++generation.current;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, accountId, selected, retry]);
  function choose(item: StockChoice) {
    ++generation.current;
    setQuery(item.name);
    setItems([]);
    onSelect(item);
  }
  return (
    <div className="space-y-3">
      <label className="block space-y-2 text-sm">
        <span>股票名称或代码</span>
        <input
          aria-label="股票名称或代码"
          role="combobox"
          aria-expanded={items.length > 0}
          aria-controls="portfolio-stock-results"
          aria-autocomplete="list"
          aria-activedescendant={
            items.length ? `portfolio-stock-${highlight}` : undefined
          }
          className="w-full rounded-lg border border-line bg-surface px-3 py-3"
          autoComplete="off"
          maxLength={64}
          placeholder="例如：中国神华 / 601088"
          value={query}
          disabled={disabled}
          onChange={(e) => {
            ++generation.current;
            setQuery(e.target.value);
            setItems([]);
            setFailed(false);
            onSelect(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" && items.length) {
              e.preventDefault();
              setHighlight((i) => (i + 1) % items.length);
            }
            if (e.key === "ArrowUp" && items.length) {
              e.preventDefault();
              setHighlight((i) => (i + items.length - 1) % items.length);
            }
            if (e.key === "Enter") {
              e.preventDefault();
              if (items[highlight]) choose(items[highlight]);
            }
            if (e.key === "Escape") setItems([]);
          }}
        />
      </label>
      <div role="status" className="text-xs text-muted">
        {loading
          ? "正在搜索…"
          : !selected && query.trim() && !items.length && !failed
            ? "未找到已收录的A股，请换名称或代码。"
            : ""}
      </div>
      {failed ? (
        <button
          type="button"
          className="text-sm text-jade-deep underline"
          onClick={() => setRetry((n) => n + 1)}
        >
          搜索失败，点击重试
        </button>
      ) : null}
      {!!items.length && (
        <div
          id="portfolio-stock-results"
          role="listbox"
          className="max-h-64 overflow-y-auto rounded-lg border border-line"
        >
          {items.map((item, i) => (
            <button
              key={item.code}
              id={`portfolio-stock-${i}`}
              type="button"
              role="option"
              aria-selected={i === highlight}
              className={`block w-full px-4 py-3 text-left text-sm hover:bg-jade/10 ${i === highlight ? "bg-jade/10" : ""}`}
              onClick={() => choose(item)}
            >
              <strong>{item.name}</strong> · {item.code} · {item.exchange}
              {!item.is_active ? " · 非活跃标的" : ""}
            </button>
          ))}
        </div>
      )}
      {selected ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-jade/10 p-4 text-sm">
          <div>
            <strong>{selected.name}</strong>
            <p className="mt-1 text-muted">{selected.code} · A股 · 人民币</p>
          </div>
          <a
            href={`/stocks/${selected.code}#dividend`}
            target="_blank"
            rel="noreferrer"
            className="text-jade-deep underline"
          >
            分红档案 ↗
          </a>
        </div>
      ) : null}
    </div>
  );
}
