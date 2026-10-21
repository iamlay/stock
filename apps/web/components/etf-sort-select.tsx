"use client";

export function EtfSortSelect({
  value,
  category,
  query,
}: {
  value: string;
  category?: string;
  query?: string;
}) {
  return (
    <form method="get" action="/etf">
      {category ? <input type="hidden" name="category" value={category} /> : null}
      {query ? <input type="hidden" name="q" value={query} /> : null}
      <select
        name="sort"
        defaultValue={value}
        onChange={(event) => event.currentTarget.form?.requestSubmit()}
        className="rounded-sm border border-line bg-surface px-2 py-1.5 text-xs text-ink-soft"
      >
        <option value="aum">按规模</option>
        <option value="change">按涨跌</option>
        <option value="yield">按股息率</option>
        <option value="code">按代码</option>
      </select>
    </form>
  );
}
