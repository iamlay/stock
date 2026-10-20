"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function ComparePicker({
  options,
  selected,
  days,
}: {
  options: { code: string; name: string }[];
  selected: string[];
  days: number;
}) {
  const router = useRouter();
  const [codes, setCodes] = useState(selected);
  const [range, setRange] = useState(days);
  const [error, setError] = useState<string | null>(null);

  function toggle(code: string) {
    setError(null);
    setCodes((current) => {
      if (current.includes(code)) return current.filter((item) => item !== code);
      if (current.length >= 5) {
        setError("最多对比 5 只 ETF");
        return current;
      }
      return [...current, code];
    });
  }

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (codes.length < 2) {
      setError("至少选择 2 只 ETF");
      return;
    }
    router.push(`/etf/compare?codes=${codes.join(",")}&days=${range}`);
  }

  return (
    <form onSubmit={onSubmit} className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-medium text-ink">选择对比标的</h2>
          <p className="mt-0.5 text-xs text-muted">2–5 只，归一化到 100</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={range}
            onChange={(event) => setRange(Number(event.target.value))}
            className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs"
          >
            <option value={60}>近 3 月</option>
            <option value={120}>近 6 月</option>
            <option value={250}>近 1 年</option>
            <option value={500}>近 2 年</option>
          </select>
          <button
            type="submit"
            className="rounded-sm bg-ink px-4 py-1.5 text-xs text-paper hover:bg-jade-deep"
          >
            对比
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {options.map((option) => {
          const checked = codes.includes(option.code);
          return (
            <label
              key={option.code}
              className={`flex cursor-pointer items-center gap-2 rounded-sm border px-3 py-2 text-xs ${
                checked
                  ? "border-jade bg-jade-soft text-jade-deep"
                  : "border-line bg-surface text-ink-soft hover:border-ink"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(option.code)}
                className="accent-[#0b7a5c]"
              />
              <span className="truncate">
                {option.name}
                <span className="ml-1 text-muted">{option.code}</span>
              </span>
            </label>
          );
        })}
      </div>
      {error ? <p className="mt-2 text-xs text-loss">{error}</p> : null}
    </form>
  );
}
